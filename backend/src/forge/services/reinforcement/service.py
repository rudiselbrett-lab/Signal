"""Reinforcement service: generation, review flow, grading, mastery."""

import random
from datetime import UTC, datetime, timedelta
from typing import Protocol
from uuid import UUID

import structlog

from forge.adapters.persistence.models.content import Article
from forge.adapters.persistence.models.knowledge import KnowledgeCard
from forge.adapters.persistence.models.reinforcement import (
    CardType,
    ItemStatus,
    ReviewAttempt,
    ReviewItem,
    ReviewSession,
)
from forge.api.errors import ConflictError, NotFoundError
from forge.domain.content import ArticleStatus
from forge.domain.reinforcement import (
    CardState,
    is_item_mastered,
)
from forge.domain.reinforcement import (
    review as sm2_review,
)
from forge.domain.reinforcement.scheduler import FUZZ_RATIO
from forge.events import publish
from forge.events.catalog import ReviewCompleted
from forge.services.ports import LLMPort
from forge.services.reinforcement.prompts import (
    GENERATE_PROMPT_VERSION,
    GENERATE_SYSTEM,
    GRADE_PROMPT_VERSION,
    GRADE_SYSTEM,
    GeneratedItems,
    GradeResult,
    build_generate_user,
    build_grade_user,
)

logger = structlog.get_logger(__name__)

MCQ_SLOW_MS = 30_000
DAILY_REVIEW_CAP = 40


class CardNotReadyError(Exception):
    """Extraction hasn't produced the knowledge card yet; retry later."""


class ReinforcementRepository(Protocol):
    async def get_article(self, user_id: UUID, article_id: UUID) -> Article | None: ...
    async def get_card(self, user_id: UUID, article_id: UUID) -> KnowledgeCard | None: ...
    async def list_items_for_article(self, user_id: UUID, article_id: UUID) -> list[ReviewItem]: ...
    async def add_items(self, items: list[ReviewItem]) -> None: ...
    async def get_item(self, user_id: UUID, item_id: UUID) -> ReviewItem | None: ...
    async def list_due_items(
        self, user_id: UUID, now: datetime, limit: int
    ) -> list[ReviewItem]: ...
    async def count_due_items(self, user_id: UUID, now: datetime) -> int: ...
    async def add_session(self, session: ReviewSession) -> ReviewSession: ...
    async def get_session(self, user_id: UUID, session_id: UUID) -> ReviewSession | None: ...
    async def add_attempt(self, attempt: ReviewAttempt) -> ReviewAttempt: ...
    async def articles_with_due_items(self, user_id: UUID, now: datetime) -> list[UUID]: ...


class ReinforcementService:
    def __init__(
        self,
        repo: ReinforcementRepository,
        llm: LLMPort,
        rng: random.Random | None = None,
    ) -> None:
        self._repo = repo
        self._llm = llm
        self._rng = rng or random.Random()

    # --- generation ------------------------------------------------------

    async def generate_items(self, user_id: UUID, article_id: UUID) -> list[ReviewItem]:
        """Called on article.read. Idempotent: skips if items already exist."""
        article = await self._repo.get_article(user_id, article_id)
        if article is None:
            return []
        existing = await self._repo.list_items_for_article(user_id, article_id)
        if existing:
            return existing
        card = await self._repo.get_card(user_id, article_id)
        if card is None:
            # Extraction is still in flight; the task layer retries with backoff.
            raise CardNotReadyError(str(article_id))

        generated = await self._llm.complete_structured(
            prompt_name=GENERATE_PROMPT_VERSION,
            system=GENERATE_SYSTEM,
            user=build_generate_user(
                article.title, card.summary, card.key_ideas, card.mental_models, card.frameworks
            ),
            schema=GeneratedItems,
            max_tokens=3000,
        )
        now = datetime.now(UTC)
        items = []
        for gi in generated.items:
            if gi.card_type == CardType.MULTIPLE_CHOICE and (
                not gi.options or len(gi.options) != 4 or gi.correct_option is None
            ):
                continue  # malformed MCQ; keep the rest
            items.append(
                ReviewItem(
                    user_id=user_id,
                    article_id=article_id,
                    card_type=gi.card_type,
                    prompt={
                        "question": gi.question,
                        "options": gi.options,
                        "correct_option": gi.correct_option,
                        "expected_points": gi.expected_points,
                        "anchor": gi.anchor,
                    },
                    due_at=now + timedelta(days=1),  # first ladder step
                )
            )
        await self._repo.add_items(items)
        logger.info("reviews.generated", article_id=str(article_id), count=len(items))
        return items

    # --- review flow -----------------------------------------------------

    async def due_items(self, user_id: UUID, limit: int = DAILY_REVIEW_CAP) -> list[ReviewItem]:
        return await self._repo.list_due_items(user_id, datetime.now(UTC), limit)

    async def due_count(self, user_id: UUID) -> int:
        return await self._repo.count_due_items(user_id, datetime.now(UTC))

    async def start_session(self, user_id: UUID) -> ReviewSession:
        session = ReviewSession(user_id=user_id, started_at=datetime.now(UTC))
        return await self._repo.add_session(session)

    async def submit_answer(
        self,
        user_id: UUID,
        session_id: UUID,
        item_id: UUID,
        answer: str | None,
        choice_index: int | None,
        latency_ms: int = 0,
    ) -> tuple[ReviewAttempt, ReviewItem]:
        item = await self._repo.get_item(user_id, item_id)
        if item is None:
            raise NotFoundError("review item not found")
        if item.status != ItemStatus.ACTIVE:
            raise ConflictError(f"item is {item.status}")
        session = await self._repo.get_session(user_id, session_id)
        if session is None:
            raise NotFoundError("session not found")

        grade, feedback, answer_text = await self._grade(item, answer, choice_index, latency_ms)

        now = datetime.now(UTC)
        state = CardState(
            ease_factor=item.ease_factor,
            interval_days=item.interval_days,
            repetitions=item.repetitions,
            lapses=item.lapses,
        )
        outcome = sm2_review(state, grade, now, fuzz=self._rng.uniform(-FUZZ_RATIO, FUZZ_RATIO))
        item.ease_factor = outcome.state.ease_factor
        item.interval_days = outcome.state.interval_days
        item.repetitions = outcome.state.repetitions
        item.lapses = outcome.state.lapses
        item.due_at = outcome.due_at
        item.consecutive_correct = item.consecutive_correct + 1 if grade >= 3 else 0
        if outcome.suspended:
            item.status = ItemStatus.SUSPENDED

        attempt = ReviewAttempt(
            user_id=user_id,
            review_item_id=item.id,
            session_id=session_id,
            answered_at=now,
            user_answer=answer_text,
            grade=grade,
            feedback=feedback,
            latency_ms=latency_ms,
        )
        await self._repo.add_attempt(attempt)
        session.items_total += 1
        if grade >= 3:
            session.items_correct += 1

        await self._update_article_status(user_id, item.article_id, now)
        publish(
            ReviewCompleted(
                review_item_id=str(item.id),
                article_id=str(item.article_id),
                user_id=str(user_id),
                grade=grade,
            )
        )
        return attempt, item

    async def finish_session(self, user_id: UUID, session_id: UUID) -> ReviewSession:
        session = await self._repo.get_session(user_id, session_id)
        if session is None:
            raise NotFoundError("session not found")
        session.finished_at = datetime.now(UTC)
        return session

    async def _grade(
        self, item: ReviewItem, answer: str | None, choice_index: int | None, latency_ms: int
    ) -> tuple[int, str | None, str | None]:
        if item.card_type == CardType.MULTIPLE_CHOICE:
            if choice_index is None:
                raise ConflictError("multiple_choice answers require choice_index")
            correct = choice_index == item.prompt.get("correct_option")
            grade = (4 if latency_ms > MCQ_SLOW_MS else 5) if correct else 1
            options = item.prompt.get("options") or []
            answer_text = (
                options[choice_index] if choice_index < len(options) else str(choice_index)
            )
            feedback = (
                None if correct else f"Correct answer: {options[item.prompt['correct_option']]}"
            )
            return grade, feedback, answer_text

        if not answer or not answer.strip():
            return 0, "No answer given.", answer
        result = await self._llm.complete_structured(
            prompt_name=GRADE_PROMPT_VERSION,
            system=GRADE_SYSTEM,
            user=build_grade_user(
                item.prompt.get("question", ""), item.prompt.get("expected_points", []), answer
            ),
            schema=GradeResult,
            max_tokens=500,
        )
        return result.grade, result.feedback, answer

    async def _update_article_status(self, user_id: UUID, article_id: UUID, now: datetime) -> None:
        article = await self._repo.get_article(user_id, article_id)
        if article is None:
            return
        items = await self._repo.list_items_for_article(user_id, article_id)
        active = [i for i in items if i.status == ItemStatus.ACTIVE]
        if active and all(
            is_item_mastered(
                CardState(i.ease_factor, i.interval_days, i.repetitions, i.lapses),
                i.consecutive_correct,
            )
            for i in active
        ):
            if article.status in (ArticleStatus.LEARNED, ArticleStatus.REVIEW_DUE):
                article.status = ArticleStatus.MASTERED
            return
        due_now = any(i.due_at <= now for i in active)
        if not due_now and article.status == ArticleStatus.REVIEW_DUE:
            article.status = ArticleStatus.LEARNED

    async def materialize_due_statuses(self, user_id: UUID) -> int:
        """Daily task: flip learned → review_due for articles with due items."""
        now = datetime.now(UTC)
        article_ids = await self._repo.articles_with_due_items(user_id, now)
        flipped = 0
        for article_id in article_ids:
            article = await self._repo.get_article(user_id, article_id)
            if article is not None and article.status == ArticleStatus.LEARNED:
                article.status = ArticleStatus.REVIEW_DUE
                flipped += 1
        return flipped
