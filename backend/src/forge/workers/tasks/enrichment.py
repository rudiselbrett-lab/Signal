"""Enrichment tasks: scoring, knowledge extraction, embeddings."""

import asyncio
from uuid import UUID

from forge.adapters.llm import AnthropicLLM
from forge.adapters.persistence.db import session_scope
from forge.adapters.persistence.repositories.scoring import SqlScoringRepository
from forge.services.scoring.service import NullSimilaritySignals, ScoringService
from forge.workers.celery_app import celery_app


@celery_app.task(
    name="forge.enrichment.score_article",
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_kwargs={"max_retries": 3},
)
def score_article(article_id: str, user_id: str) -> None:
    asyncio.run(_score_article(UUID(article_id), UUID(user_id)))


async def _score_article(article_id: UUID, user_id: UUID) -> None:
    async with session_scope() as session:
        service = ScoringService(
            repo=SqlScoringRepository(session),
            llm=AnthropicLLM(),
            signals=NullSimilaritySignals(),
        )
        await service.score_article(user_id, article_id)
