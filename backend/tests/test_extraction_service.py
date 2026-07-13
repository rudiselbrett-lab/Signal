import uuid

import pytest

from forge.adapters.persistence.models.content import Article
from forge.adapters.persistence.models.knowledge import ArticleEntity, Entity
from forge.config import DEFAULT_USER_ID
from forge.domain.content import EnrichmentStatus
from forge.domain.knowledge import EntityKind, normalize_entity_name
from forge.domain.scoring import Difficulty
from forge.events import bus
from forge.services.extraction.prompts import ExtractedKnowledge, KeyIdea, NamedEntity
from forge.services.extraction.service import ExtractionService

USER = DEFAULT_USER_ID


class FakeKnowledgeRepo:
    def __init__(self, article):
        self.article = article
        self.cards = {}
        self.entities = {}
        self.links = []

    async def get_article(self, user_id, article_id):
        return self.article if self.article.id == article_id else None

    async def get_card(self, user_id, article_id):
        return self.cards.get(article_id)

    async def add_card(self, card):
        card.id = card.id or uuid.uuid4()
        self.cards[card.article_id] = card
        return card

    async def get_or_create_entity(self, user_id, kind, name, normalized_name):
        key = (kind, normalized_name)
        if key not in self.entities:
            entity = Entity(
                id=uuid.uuid4(),
                user_id=user_id,
                kind=kind,
                name=name,
                normalized_name=normalized_name,
            )
            self.entities[key] = entity
        return self.entities[key]

    async def link_entity(self, user_id, article_id, entity_id, salience):
        link = ArticleEntity(
            user_id=user_id, article_id=article_id, entity_id=entity_id, salience=salience
        )
        self.links.append(link)
        return link


class FakeLLM:
    def __init__(self, result=None, error=None):
        self.result = result
        self.error = error
        self.calls = 0

    async def complete_structured(self, **kwargs):
        self.calls += 1
        if self.error:
            raise self.error
        return self.result


EXTRACTED = ExtractedKnowledge(
    summary="A summary of gateway scaling.",
    key_ideas=[KeyIdea(idea="Cache token auth at the edge", quote="we cache tokens at the edge")],
    mental_models=["Backpressure"],
    frameworks=["Strangler Fig"],
    entities=[
        NamedEntity(name="Stripe", kind="company"),
        NamedEntity(name="stripe", kind="company"),  # duplicate after normalization
        NamedEntity(name="Envoy", kind="product"),
        NamedEntity(name="Weird Kind", kind="alien"),  # unknown kind → skipped
    ],
    topics=["API Gateways", "scaling"],
    difficulty=Difficulty.INTERMEDIATE,
)


@pytest.fixture(autouse=True)
def clean_bus():
    bus.clear_subscribers()
    yield
    bus.clear_subscribers()


@pytest.fixture
def article():
    return Article(
        id=uuid.uuid4(),
        user_id=USER,
        url="https://example.com/a",
        canonical_url="https://example.com/a",
        title="Scaling API gateways",
        full_text="we cache tokens at the edge " * 50,
        status="unread",
        enrichment_status=EnrichmentStatus.FETCHED,
    )


async def test_extraction_builds_card_and_normalized_entities(article):
    repo = FakeKnowledgeRepo(article)
    service = ExtractionService(repo, FakeLLM(EXTRACTED))
    seen = []
    bus.subscribe("article.enriched", seen.append)

    card = await service.extract(USER, article.id)

    assert card.summary.startswith("A summary")
    assert card.topics == ["api-gateways", "scaling"]
    assert article.enrichment_status == EnrichmentStatus.ENRICHED
    assert len(seen) == 1

    kinds = {(e.kind, e.normalized_name) for e in repo.entities.values()}
    assert (EntityKind.TOPIC, "api gateways") in kinds
    assert (EntityKind.MENTAL_MODEL, "backpressure") in kinds
    assert (EntityKind.FRAMEWORK, "strangler fig") in kinds
    assert (EntityKind.COMPANY, "stripe") in kinds
    assert (EntityKind.PRODUCT, "envoy") in kinds
    # 2 topics + 1 mental model + 1 framework + 2 entities
    # (duplicate Stripe collapsed, unknown kind skipped)
    assert len(repo.links) == 6


async def test_extraction_is_idempotent_per_version(article):
    repo = FakeKnowledgeRepo(article)
    llm = FakeLLM(EXTRACTED)
    service = ExtractionService(repo, llm)

    first = await service.extract(USER, article.id)
    second = await service.extract(USER, article.id)
    assert first is second
    assert llm.calls == 1


async def test_extraction_failure_marks_article_failed(article):
    repo = FakeKnowledgeRepo(article)
    service = ExtractionService(repo, FakeLLM(error=RuntimeError("llm down")))

    with pytest.raises(RuntimeError):
        await service.extract(USER, article.id)
    assert article.enrichment_status == EnrichmentStatus.FAILED
    assert "extraction" in article.enrichment_error


def test_normalize_entity_name():
    assert normalize_entity_name("  API-Gateways ") == "api gateways"
    assert normalize_entity_name("Stripe, Inc.") == "stripe inc"
