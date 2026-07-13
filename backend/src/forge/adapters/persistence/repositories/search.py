from dataclasses import dataclass
from typing import Any
from uuid import UUID

from sqlalchemy import delete, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from forge.adapters.persistence.models.content import Article
from forge.adapters.persistence.models.knowledge import KnowledgeCard
from forge.adapters.persistence.models.search import ArticleChunk


@dataclass(frozen=True)
class SearchHit:
    chunk_id: UUID
    article_id: UUID
    chunk_index: int
    chunk_text: str
    score: float
    article_title: str
    article_url: str


class SqlSearchRepository:
    """Embeddings persistence + the hybrid_search SQL function (RRF fusion)."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_article(self, user_id: UUID, article_id: UUID) -> Article | None:
        stmt = select(Article).where(Article.user_id == user_id, Article.id == article_id)
        result: Article | None = await self._session.scalar(stmt)
        return result

    async def get_card(self, user_id: UUID, article_id: UUID) -> KnowledgeCard | None:
        stmt = select(KnowledgeCard).where(
            KnowledgeCard.user_id == user_id, KnowledgeCard.article_id == article_id
        )
        result: KnowledgeCard | None = await self._session.scalar(stmt)
        return result

    async def replace_chunks(self, article_id: UUID, chunks: list[ArticleChunk]) -> None:
        await self._session.execute(
            delete(ArticleChunk).where(ArticleChunk.article_id == article_id)
        )
        self._session.add_all(chunks)
        await self._session.flush()

    async def hybrid_search(
        self,
        user_id: UUID,
        query: str,
        query_embedding: list[float],
        limit: int = 12,
        per_article: int = 3,
    ) -> list[SearchHit]:
        stmt = text(
            """
            SELECT h.chunk_id, h.article_id, h.chunk_index, h.chunk_text, h.score,
                   a.title AS article_title, a.url AS article_url
            FROM hybrid_search(:user_id, :query, CAST(:embedding AS vector), :limit, :per_article) h
            JOIN articles a ON a.id = h.article_id
            ORDER BY h.score DESC
            """
        )
        rows = await self._session.execute(
            stmt,
            {
                "user_id": str(user_id),
                "query": query,
                "embedding": str(query_embedding),
                "limit": limit,
                "per_article": per_article,
            },
        )
        return [SearchHit(**dict(row._mapping)) for row in rows]

    async def max_similarity_to_library(
        self, user_id: UUID, embedding: list[float], statuses: list[str]
    ) -> float | None:
        stmt = text(
            """
            SELECT MAX(1 - (embedding <=> CAST(:embedding AS vector))) AS sim
            FROM articles
            WHERE user_id = :user_id AND embedding IS NOT NULL AND status = ANY(:statuses)
            """
        )
        row: Any = await self._session.execute(
            stmt,
            {"user_id": str(user_id), "embedding": str(embedding), "statuses": statuses},
        )
        value = row.scalar()
        return float(value) if value is not None else None
