"""Embeddings service: enriched article → chunk + whole-article vectors."""

from typing import Protocol
from uuid import UUID

import structlog

from forge.adapters.persistence.models.content import Article
from forge.adapters.persistence.models.knowledge import KnowledgeCard
from forge.adapters.persistence.models.search import ArticleChunk
from forge.domain.knowledge.chunking import chunk_text, contextualize
from forge.services.ports import EmbeddingPort

logger = structlog.get_logger(__name__)

EMBEDDING_VERSION = "te3l-1536-v1"


class EmbeddingsRepository(Protocol):
    async def get_article(self, user_id: UUID, article_id: UUID) -> Article | None: ...
    async def get_card(self, user_id: UUID, article_id: UUID) -> KnowledgeCard | None: ...
    async def replace_chunks(self, article_id: UUID, chunks: list[ArticleChunk]) -> None: ...


class EmbeddingsService:
    def __init__(self, repo: EmbeddingsRepository, embedder: EmbeddingPort) -> None:
        self._repo = repo
        self._embed = embedder

    async def embed_article(self, user_id: UUID, article_id: UUID) -> int:
        """Returns the number of chunks embedded. Idempotent per version."""
        article = await self._repo.get_article(user_id, article_id)
        if article is None or not article.full_text:
            return 0
        if article.embedding_version == EMBEDDING_VERSION and article.embedding is not None:
            return 0

        chunks = chunk_text(article.full_text)
        card = await self._repo.get_card(user_id, article_id)
        whole_article_text = self._whole_article_text(article, card)

        texts = [contextualize(article.title, c) for c in chunks] + [whole_article_text]
        vectors = await self._embed.embed(texts)

        chunk_rows = [
            ArticleChunk(
                user_id=user_id,
                article_id=article_id,
                chunk_index=chunk.index,
                text=chunk.text,
                token_count=len(chunk.text) // 4,
                embedding=vectors[i],
            )
            for i, chunk in enumerate(chunks)
        ]
        await self._repo.replace_chunks(article_id, chunk_rows)
        article.embedding = vectors[-1]
        article.embedding_version = EMBEDDING_VERSION
        logger.info("embeddings.done", article_id=str(article_id), chunks=len(chunk_rows))
        return len(chunk_rows)

    def _whole_article_text(self, article: Article, card: KnowledgeCard | None) -> str:
        parts = [article.title]
        if card is not None:
            parts.append(card.summary)
            parts.extend(ki.get("idea", "") for ki in card.key_ideas)
        elif article.teaser:
            parts.append(article.teaser[:1000])
        else:
            parts.append((article.full_text or "")[:1000])
        return "\n".join(p for p in parts if p)
