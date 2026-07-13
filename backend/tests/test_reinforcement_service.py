import random
import uuid
from datetime import UTC, datetime, timedelta

import pytest

from forge.adapters.persistence.models.content import Article
from forge.adapters.persistence.models.knowledge import KnowledgeCard
from forge.adapters.persistence.models.reinforcement import CardType, ItemStatus
from forge.config import DEFAULT_USER_ID
from forge.domain.content import ArticleStatus
from forge.events import bus
from forge.services.reinforcement.prompts import GeneratedItem, GeneratedItems, GradeResult
from forge.services.reinforcement.service import CardNotReadyError, ReinforcementService

USER = DEFAULT_USER_ID


class FakeRepo:
    def __init__(self, article=None, card=None):
        self.article = article
        self.card = card
        self.items = {}
        self.sessions = {}
        self.attempts = []

    async def get_article(self, user_id, article_id):
        return self.article

    async def get_card(self, user_id, article_id):
        return self.card

    async def list_items_for_article(self, user_id, article_id):
        return [i for i in self.items.values() if i.article_id == article_id]

    async def add_items(self, items):
        for item in items:
            item.id = item.id or uuid.uuid4()
            item.status = item.status or ItemStatus.ACTIVE
            item.ease_factor = item.ease_factor or 2.5
            item.interval_days = item.interval_days or 0.0
            item.repetitions = item.repetitions or 0
            item.lapses = item.lapses or 0
            item.consecutive_correct = item.consecutive_correct or 0
            self.items[item.id] = item

    async def get_item(self, user_id, item_id):
        return self.items.get(item_id)

    async def list_due_items(self, user_id, now, limit):
        due = [i for i in self.items.values() if i.status == ItemStatus.ACTIVE and i.due_at <= now]
        return sorted(due, key=lambda i: i.due_at)[:limit]

    async def count_due_items(self, user_id, now):
        return len(await self.list_due_items(user_id, now, 10_000))

    async def add_session(self, session):
        session.id = session.id or uuid.uuid4()
        session.items_total = session.items_total or 0
        session.items_correct = session.items_correct or 0
        self.sessions[session.id] = session
        return session

    async def get_session(self, user_id, session_id):
        return self.sessions.get(session_id)

    async def add_attempt(self, attempt):
        self.attempts.append(attempt)
        return attempt

    async def articles_with_due_items(self, user_id, now):
        return list({i.article_id for i in await self.list_due_items(user_id, now, 10_000)})


class FakeLLM:
    def __init__(self, generated=None, grade=None):
        self.generated = generated
        self.grade = grade
        self.calls = []

    async def complete_structured(self, *, prompt_name, schema, **kwargs):
        self.calls.append(prompt_name)
        if schema is GeneratedItems:
            return self.generated
        return self.grade


GENERATED = GeneratedItems(
    items=[
        GeneratedItem(
            card_type=CardType.QUICK_RECALL,
            question="What does edge token caching improve?",
            expected_points=["reduces auth latency"],
            anchor="Cache token auth at the edge",
        ),
        GeneratedItem(
            card_type=CardType.MULTIPLE_CHOICE,
            question="Which pattern was used?",
            options=["Strangler Fig", "Big Bang", "Blue-Green", "Canary"],
            correct_option=0,
            expected_points=["strangler fig"],
            anchor="Strangler Fig",
        ),
        GeneratedItem(
            card_type=CardType.MULTIPLE_CHOICE,
            question="Malformed MCQ",  # only 2 options → dropped by validation
            options=["a", "b"],
            correct_option=0,
            expected_points=["x"],
            anchor="y",
        ),
        GeneratedItem(
            card_type=CardType.EXPLAIN,
            question="Explain backpressure in your own words.",
            expected_points=["consumers signal producers", "prevents overload"],
            anchor="Backpressure",
        ),
    ]
)


def make_article(status=ArticleStatus.LEARNED):
    return Article(
        id=uuid.uuid4(),
        user_id=USER,
        url="https://example.com/a",
        canonical_url="https://example.com/a",
        title="A",
        status=status,
    )


def make_card(article):
    return KnowledgeCard(
        id=uuid.uuid4(),
        user_id=USER,
        article_id=article.id,
        summary="s",
        key_ideas=[{"idea": "Cache token auth at the edge", "quote": "q"}],
        mental_models=["Backpressure"],
        frameworks=["Strangler Fig"],
        topics=["api-gateways"],
        tags=[],
        difficulty="intermediate",
    )


@pytest.fixture(autouse=True)
def clean_bus():
    bus.clear_subscribers()
    yield
    bus.clear_subscribers()


async def test_generation_creates_items_and_drops_malformed_mcq():
    article = make_article()
    repo = FakeRepo(article=article, card=make_card(article))
    svc = ReinforcementService(repo, FakeLLM(generated=GENERATED))

    items = await svc.generate_items(USER, article.id)

    assert len(items) == 3  # malformed MCQ dropped
    assert all(i.due_at is not None for i in items)
    # Idempotent: second call returns existing without another LLM call.
    again = await svc.generate_items(USER, article.id)
    assert len(again) == 3


async def test_generation_waits_for_knowledge_card():
    article = make_article()
    repo = FakeRepo(article=article, card=None)
    svc = ReinforcementService(repo, FakeLLM(generated=GENERATED))
    with pytest.raises(CardNotReadyError):
        await svc.generate_items(USER, article.id)


async def test_mcq_graded_in_code_correct_and_fast():
    article = make_article()
    repo = FakeRepo(article=article, card=make_card(article))
    svc = ReinforcementService(repo, FakeLLM(generated=GENERATED), rng=random.Random(1))
    items = await svc.generate_items(USER, article.id)
    mcq = next(i for i in items if i.card_type == CardType.MULTIPLE_CHOICE)
    for item in items:
        item.due_at = datetime.now(UTC) - timedelta(hours=1)
    session = await svc.start_session(USER)

    attempt, updated = await svc.submit_answer(
        USER, session.id, mcq.id, answer=None, choice_index=0, latency_ms=5000
    )
    assert attempt.grade == 5
    assert updated.repetitions == 1
    assert 0.9 <= updated.interval_days <= 1.1  # first ladder step ± fuzz

    wrong_session_stats = repo.sessions[session.id]
    assert wrong_session_stats.items_total == 1
    assert wrong_session_stats.items_correct == 1


async def test_mcq_wrong_answer_resets_and_gives_feedback():
    article = make_article()
    repo = FakeRepo(article=article, card=make_card(article))
    svc = ReinforcementService(repo, FakeLLM(generated=GENERATED), rng=random.Random(1))
    items = await svc.generate_items(USER, article.id)
    mcq = next(i for i in items if i.card_type == CardType.MULTIPLE_CHOICE)
    session = await svc.start_session(USER)

    attempt, updated = await svc.submit_answer(
        USER, session.id, mcq.id, answer=None, choice_index=2, latency_ms=5000
    )
    assert attempt.grade == 1
    assert "Strangler Fig" in attempt.feedback
    assert updated.lapses == 1
    assert updated.consecutive_correct == 0


async def test_open_ended_graded_by_llm():
    article = make_article()
    repo = FakeRepo(article=article, card=make_card(article))
    llm = FakeLLM(
        generated=GENERATED, grade=GradeResult(grade=4, feedback="Good, missed overload.")
    )
    svc = ReinforcementService(repo, llm, rng=random.Random(1))
    items = await svc.generate_items(USER, article.id)
    explain = next(i for i in items if i.card_type == CardType.EXPLAIN)
    session = await svc.start_session(USER)

    attempt, _ = await svc.submit_answer(
        USER,
        session.id,
        explain.id,
        answer="consumers tell producers to slow down",
        choice_index=None,
    )
    assert attempt.grade == 4
    assert "reviews.grade.v1" in llm.calls


async def test_empty_open_answer_grades_zero_without_llm():
    article = make_article()
    repo = FakeRepo(article=article, card=make_card(article))
    llm = FakeLLM(generated=GENERATED, grade=GradeResult(grade=5, feedback="unused"))
    svc = ReinforcementService(repo, llm, rng=random.Random(1))
    items = await svc.generate_items(USER, article.id)
    explain = next(i for i in items if i.card_type == CardType.EXPLAIN)
    session = await svc.start_session(USER)

    attempt, _ = await svc.submit_answer(
        USER, session.id, explain.id, answer="  ", choice_index=None
    )
    assert attempt.grade == 0
    assert "reviews.grade.v1" not in llm.calls


async def test_article_masters_when_all_items_mature():
    article = make_article(status=ArticleStatus.REVIEW_DUE)
    repo = FakeRepo(article=article, card=make_card(article))
    llm = FakeLLM(generated=GENERATED, grade=GradeResult(grade=5, feedback="perfect"))
    svc = ReinforcementService(repo, llm, rng=random.Random(1))
    items = await svc.generate_items(USER, article.id)
    # Fast-forward every item to the edge of mastery.
    for item in items:
        item.interval_days = 35.0
        item.repetitions = 5
        item.consecutive_correct = 2
        item.ease_factor = 2.5
    session = await svc.start_session(USER)

    explain = next(i for i in items if i.card_type == CardType.EXPLAIN)
    await svc.submit_answer(USER, session.id, explain.id, answer="great answer", choice_index=None)

    assert article.status == ArticleStatus.MASTERED


async def test_materialize_due_flips_learned_articles():
    article = make_article(status=ArticleStatus.LEARNED)
    repo = FakeRepo(article=article, card=make_card(article))
    svc = ReinforcementService(repo, FakeLLM(generated=GENERATED), rng=random.Random(1))
    items = await svc.generate_items(USER, article.id)
    for item in items:
        item.due_at = datetime.now(UTC) - timedelta(hours=2)

    flipped = await svc.materialize_due_statuses(USER)
    assert flipped == 1
    assert article.status == ArticleStatus.REVIEW_DUE
