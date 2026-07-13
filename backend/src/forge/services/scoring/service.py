"""Scoring service: article → explainable 0-100 learning score.

Embedding-derived signals (interest similarity, novelty vs. library) come
from a SimilaritySignals port. Until the embeddings phase provides a real
implementation, the null implementation yields neutral cold-start scores —
the seam is already in place.
"""

from typing import Protocol
from uuid import UUID

import structlog

from forge.adapters.persistence.models.content import Article
from forge.adapters.persistence.models.scoring import ArticleScore
from forge.domain.content import ArticleStatus
from forge.domain.scoring import (
    SCORING_VERSION,
    ScoreBreakdown,
    score_credibility,
    score_knowledge_gap,
    score_novelty,
    score_practicality,
    score_reading_time,
    score_relevance,
)
from forge.services.ports import LLMPort
from forge.services.scoring.assessment import (
    ASSESS_PROMPT_VERSION,
    ASSESS_SYSTEM,
    QualityAssessment,
    build_assess_user,
)

logger = structlog.get_logger(__name__)


class ScoringRepository(Protocol):
    async def get_article(self, user_id: UUID, article_id: UUID) -> Article | None: ...
    async def get_score(self, user_id: UUID, article_id: UUID) -> ArticleScore | None: ...
    async def upsert_score(self, score: ArticleScore) -> ArticleScore: ...
    async def source_weights(self, article: Article) -> tuple[float, float]: ...


class SimilaritySignals(Protocol):
    async def interest_similarity(self, user_id: UUID, article: Article) -> float | None: ...
    async def max_library_similarity(self, user_id: UUID, article: Article) -> float | None: ...
    async def knowledge_gap_alignment(self, user_id: UUID, topics: list[str]) -> float | None: ...


class NullSimilaritySignals:
    """Cold-start signals until the embeddings module supplies real ones."""

    async def interest_similarity(self, user_id: UUID, article: Article) -> float | None:
        return None

    async def max_library_similarity(self, user_id: UUID, article: Article) -> float | None:
        return None

    async def knowledge_gap_alignment(self, user_id: UUID, topics: list[str]) -> float | None:
        return None


class ScoringService:
    def __init__(self, repo: ScoringRepository, llm: LLMPort, signals: SimilaritySignals) -> None:
        self._repo = repo
        self._llm = llm
        self._signals = signals

    async def score_article(self, user_id: UUID, article_id: UUID) -> ArticleScore | None:
        article = await self._repo.get_article(user_id, article_id)
        if article is None or not (article.full_text or article.teaser):
            return None
        existing = await self._repo.get_score(user_id, article_id)
        if existing is not None and existing.scoring_version == SCORING_VERSION:
            return existing

        assessment = await self._llm.complete_structured(
            prompt_name=ASSESS_PROMPT_VERSION,
            system=ASSESS_SYSTEM,
            user=build_assess_user(
                article.title,
                article.author,
                str(article.source.source_type) if article.source else "custom_url",
                article.full_text or article.teaser or "",
            ),
            schema=QualityAssessment,
        )

        source_weight, category_weight = await self._repo.source_weights(article)
        breakdown = ScoreBreakdown(
            relevance=score_relevance(
                await self._signals.interest_similarity(user_id, article),
                source_weight,
                category_weight,
            ),
            novelty=score_novelty(await self._signals.max_library_similarity(user_id, article)),
            credibility=score_credibility(
                str(article.source.source_type) if article.source else "custom_url",
                assessment.evidence_quality,
                assessment.evidence_rationale,
            ),
            practicality=score_practicality(
                assessment.practicality, assessment.practicality_rationale
            ),
            knowledge_gap=score_knowledge_gap(
                await self._signals.knowledge_gap_alignment(user_id, assessment.topics),
                assessment.knowledge_gap_estimate,
                assessment.knowledge_gap_rationale,
            ),
            reading_time_bonus=score_reading_time(article.reading_time_minutes),
        )

        score = existing or ArticleScore(user_id=user_id, article_id=article.id)
        score.overall = breakdown.overall
        score.relevance = breakdown.relevance.points
        score.novelty = breakdown.novelty.points
        score.credibility = breakdown.credibility.points
        score.practicality = breakdown.practicality.points
        score.knowledge_gap = breakdown.knowledge_gap.points
        score.reading_time_bonus = breakdown.reading_time_bonus.points
        score.difficulty = assessment.difficulty
        score.scoring_version = SCORING_VERSION
        score.rationale = {
            name: {
                "points": component.points,
                "max": component.maximum,
                "rationale": component.rationale,
            }
            for name, component in (
                ("relevance", breakdown.relevance),
                ("novelty", breakdown.novelty),
                ("credibility", breakdown.credibility),
                ("practicality", breakdown.practicality),
                ("knowledge_gap", breakdown.knowledge_gap),
                ("reading_time_bonus", breakdown.reading_time_bonus),
            )
        } | {"topics": assessment.topics}
        if existing is None:
            await self._repo.upsert_score(score)

        # Freshly scored discoveries surface in the suggested queue.
        if article.status == ArticleStatus.DISCOVERED:
            article.status = ArticleStatus.SUGGESTED
        logger.info("scoring.done", article_id=str(article_id), overall=score.overall)
        return score
