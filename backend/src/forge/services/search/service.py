"""Search service: one hybrid retrieval path shared by global search,
related-articles, and the coach's RAG pipeline."""

from typing import Protocol
from uuid import UUID

from forge.adapters.persistence.repositories.search import SearchHit
from forge.services.ports import EmbeddingPort


class SearchRepository(Protocol):
    async def hybrid_search(
        self,
        user_id: UUID,
        query: str,
        query_embedding: list[float],
        limit: int = 12,
        per_article: int = 3,
    ) -> list[SearchHit]: ...


class SearchService:
    def __init__(self, repo: SearchRepository, embedder: EmbeddingPort) -> None:
        self._repo = repo
        self._embed = embedder

    async def search(
        self, user_id: UUID, query: str, limit: int = 12, per_article: int = 3
    ) -> list[SearchHit]:
        query = query.strip()
        if not query:
            return []
        [query_embedding] = await self._embed.embed([query])
        return await self._repo.hybrid_search(
            user_id, query, query_embedding, limit=limit, per_article=per_article
        )
