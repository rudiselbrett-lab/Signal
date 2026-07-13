"""Embedding-backed similarity signals for scoring.

Novelty is live as soon as the library has embeddings. Interest similarity
and knowledge-gap alignment stay None until the analytics module produces an
interest profile and topic mastery (they degrade to neutral priors).
"""

from uuid import UUID

from forge.adapters.persistence.models.content import Article
from forge.adapters.persistence.repositories.search import SqlSearchRepository
from forge.domain.content import LIBRARY_STATUSES
from forge.services.ports import EmbeddingPort


class SqlSimilaritySignals:
    def __init__(self, repo: SqlSearchRepository, embedder: EmbeddingPort) -> None:
        self._repo = repo
        self._embed = embedder
        self._candidate_embedding: list[float] | None = None

    async def _embedding_for(self, article: Article) -> list[float]:
        """Candidate articles are scored before enrichment, so embed a cheap
        preview (title + teaser/lead) on the fly; cached per service instance."""
        if self._candidate_embedding is None:
            preview = "\n".join(
                p for p in (article.title, (article.teaser or article.full_text or "")[:1500]) if p
            )
            [self._candidate_embedding] = await self._embed.embed([preview])
        return self._candidate_embedding

    async def interest_similarity(self, user_id: UUID, article: Article) -> float | None:
        return None  # provided by the analytics module (interest profile)

    async def max_library_similarity(self, user_id: UUID, article: Article) -> float | None:
        embedding = await self._embedding_for(article)
        return await self._repo.max_similarity_to_library(
            user_id, embedding, [str(s) for s in LIBRARY_STATUSES]
        )

    async def knowledge_gap_alignment(self, user_id: UUID, topics: list[str]) -> float | None:
        return None  # provided by the analytics module (topic mastery)
