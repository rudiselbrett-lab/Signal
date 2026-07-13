import uuid

import pytest

from forge.adapters.persistence.models.content import Article
from forge.config import DEFAULT_USER_ID
from forge.domain.content import ArticleStatus
from forge.domain.scoring import SCORING_VERSION, Difficulty
from forge.services.scoring.assessment import QualityAssessment
from forge.services.scoring.service import NullSimilaritySignals, ScoringService

USER = DEFAULT_USER_ID


class FakeScoringRepo:
    def __init__(self, article):
        self.article = article
        self.scores = {}

    async def get_article(self, user_id, article_id):
        return self.article if self.article.id == article_id else None

    async def get_score(self, user_id, article_id):
        return self.scores.get(article_id)

    async def upsert_score(self, score):
        score.id = score.id or uuid.uuid4()
        self.scores[score.article_id] = score
        return score

    async def source_weights(self, article):
        return 1.0, 1.0


class FakeLLM:
    def __init__(self, assessment):
        self.assessment = assessment
        self.calls = []

    async def complete_structured(self, *, prompt_name, system, user, schema, **kwargs):
        self.calls.append(prompt_name)
        return self.assessment


@pytest.fixture
def article():
    return Article(
        id=uuid.uuid4(),
        user_id=USER,
        url="https://example.com/a",
        canonical_url="https://example.com/a",
        title="Scaling API gateways",
        full_text="body " * 400,
        reading_time_minutes=8,
        status=ArticleStatus.DISCOVERED,
        source=None,
        source_id=None,
    )


ASSESSMENT = QualityAssessment(
    evidence_quality=0.8,
    evidence_rationale="Primary experience with production data",
    practicality=0.9,
    practicality_rationale="Concrete migration checklist",
    knowledge_gap_estimate=0.6,
    knowledge_gap_rationale="Specialized infrastructure knowledge",
    difficulty=Difficulty.INTERMEDIATE,
    topics=["api-gateways", "scaling"],
)


async def test_scoring_produces_explainable_breakdown(article):
    repo = FakeScoringRepo(article)
    service = ScoringService(repo, FakeLLM(ASSESSMENT), NullSimilaritySignals())

    score = await service.score_article(USER, article.id)

    assert score.scoring_version == SCORING_VERSION
    # Deterministic arithmetic given the fake assessment + cold-start signals:
    # relevance 21 + novelty 14 + credibility round(20*(.4*.6+.6*.8)) = 14
    # + practicality round(15*.9) = 14 + gap round(10*.6) = 6 + rt 5 = 74
    assert score.overall == 74
    assert score.difficulty == Difficulty.INTERMEDIATE
    components = {k: v for k, v in score.rationale.items() if isinstance(v, dict)}
    assert sum(c["points"] for c in components.values()) == score.overall
    assert all(c["rationale"] for c in components.values())
    assert score.rationale["topics"] == ["api-gateways", "scaling"]


async def test_scoring_promotes_discovered_to_suggested(article):
    repo = FakeScoringRepo(article)
    service = ScoringService(repo, FakeLLM(ASSESSMENT), NullSimilaritySignals())
    await service.score_article(USER, article.id)
    assert article.status == ArticleStatus.SUGGESTED


async def test_scoring_is_idempotent_per_version(article):
    repo = FakeScoringRepo(article)
    llm = FakeLLM(ASSESSMENT)
    service = ScoringService(repo, llm, NullSimilaritySignals())

    first = await service.score_article(USER, article.id)
    second = await service.score_article(USER, article.id)

    assert first is second
    assert llm.calls == ["assess.v1"]  # one LLM call, not two


async def test_articles_without_text_are_skipped(article):
    article.full_text = None
    article.teaser = None
    repo = FakeScoringRepo(article)
    service = ScoringService(repo, FakeLLM(ASSESSMENT), NullSimilaritySignals())
    assert await service.score_article(USER, article.id) is None
