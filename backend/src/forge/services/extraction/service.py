"""Knowledge extraction: saved article → knowledge card + normalized entities."""

from typing import Protocol
from uuid import UUID

import structlog

from forge.adapters.persistence.models.content import Article
from forge.adapters.persistence.models.knowledge import ArticleEntity, Entity, KnowledgeCard
from forge.domain.content import EnrichmentStatus
from forge.domain.knowledge import EntityKind, normalize_entity_name
from forge.events import publish
from forge.events.catalog import ArticleEnriched
from forge.services.extraction.prompts import (
    EXTRACT_PROMPT_VERSION,
    EXTRACT_SYSTEM,
    ExtractedKnowledge,
    build_extract_user,
)
from forge.services.ports import LLMPort

logger = structlog.get_logger(__name__)

EXTRACTION_VERSION = "v1"

_KIND_ALIASES = {
    "company": EntityKind.COMPANY,
    "product": EntityKind.PRODUCT,
    "framework": EntityKind.FRAMEWORK,
    "concept": EntityKind.CONCEPT,
    "mental_model": EntityKind.MENTAL_MODEL,
    "mental model": EntityKind.MENTAL_MODEL,
    "topic": EntityKind.TOPIC,
}


class KnowledgeRepository(Protocol):
    async def get_article(self, user_id: UUID, article_id: UUID) -> Article | None: ...
    async def get_card(self, user_id: UUID, article_id: UUID) -> KnowledgeCard | None: ...
    async def add_card(self, card: KnowledgeCard) -> KnowledgeCard: ...
    async def get_or_create_entity(
        self, user_id: UUID, kind: EntityKind, name: str, normalized_name: str
    ) -> Entity: ...
    async def link_entity(
        self, user_id: UUID, article_id: UUID, entity_id: UUID, salience: float
    ) -> ArticleEntity: ...


class ExtractionService:
    def __init__(self, repo: KnowledgeRepository, llm: LLMPort) -> None:
        self._repo = repo
        self._llm = llm

    async def extract(self, user_id: UUID, article_id: UUID) -> KnowledgeCard | None:
        article = await self._repo.get_article(user_id, article_id)
        if article is None or not article.full_text:
            return None
        existing = await self._repo.get_card(user_id, article_id)
        if existing is not None and existing.extraction_version == EXTRACTION_VERSION:
            return existing

        try:
            extracted = await self._llm.complete_structured(
                prompt_name=EXTRACT_PROMPT_VERSION,
                system=EXTRACT_SYSTEM,
                user=build_extract_user(article.title, article.author, article.full_text),
                schema=ExtractedKnowledge,
                max_tokens=4096,
            )
        except Exception as exc:
            article.enrichment_status = EnrichmentStatus.FAILED
            article.enrichment_error = f"extraction: {exc}"
            logger.warning("extraction.failed", article_id=str(article_id), error=str(exc))
            raise

        card = existing or KnowledgeCard(user_id=user_id, article_id=article.id)
        card.summary = extracted.summary
        card.key_ideas = [ki.model_dump() for ki in extracted.key_ideas]
        card.mental_models = extracted.mental_models
        card.frameworks = extracted.frameworks
        card.topics = [normalize_entity_name(t).replace(" ", "-") for t in extracted.topics]
        card.tags = extracted.tags
        card.difficulty = extracted.difficulty
        card.extraction_version = EXTRACTION_VERSION
        if existing is None:
            await self._repo.add_card(card)

        await self._link_entities(user_id, article.id, extracted, card.topics)
        article.enrichment_status = EnrichmentStatus.ENRICHED
        article.enrichment_error = None
        publish(ArticleEnriched(article_id=str(article.id), user_id=str(user_id)))
        logger.info("extraction.done", article_id=str(article_id), topics=card.topics)
        return card

    async def _link_entities(
        self, user_id: UUID, article_id: UUID, extracted: ExtractedKnowledge, topics: list[str]
    ) -> None:
        seen: set[tuple[EntityKind, str]] = set()

        async def link(kind: EntityKind, name: str, salience: float) -> None:
            normalized = normalize_entity_name(name)
            if not normalized or (kind, normalized) in seen:
                return
            seen.add((kind, normalized))
            entity = await self._repo.get_or_create_entity(user_id, kind, name, normalized)
            await self._repo.link_entity(user_id, article_id, entity.id, salience)

        for topic in topics:
            await link(EntityKind.TOPIC, topic, 1.0)
        for model in extracted.mental_models:
            await link(EntityKind.MENTAL_MODEL, model, 0.8)
        for framework in extracted.frameworks:
            await link(EntityKind.FRAMEWORK, framework, 0.8)
        for ne in extracted.entities:
            kind = _KIND_ALIASES.get(ne.kind.strip().lower())
            if kind is not None:
                await link(kind, ne.name, 0.6)
