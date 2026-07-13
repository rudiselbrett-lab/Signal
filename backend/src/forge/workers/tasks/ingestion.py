"""Ingestion tasks.

Async service code runs under asyncio.run inside sync Celery tasks; each
task is its own unit of work (session/transaction) and is idempotent, so
retries and duplicate deliveries are safe.
"""

import asyncio
from uuid import UUID

from forge.adapters.persistence.db import session_scope
from forge.adapters.persistence.repositories.content import SqlContentRepository
from forge.adapters.persistence.repositories.sources import SqlSourcesRepository
from forge.adapters.sources import get_adapter
from forge.config import DEFAULT_USER_ID
from forge.domain.sources import SourceType
from forge.services.ingestion.fetcher import fetch_content
from forge.services.ingestion.service import IngestionService
from forge.workers.celery_app import celery_app


def _service(session) -> IngestionService:  # type: ignore[no-untyped-def]
    return IngestionService(
        content_repo=SqlContentRepository(session),
        sources_repo=SqlSourcesRepository(session),
        adapter_for=lambda st: get_adapter(SourceType(st)),
        fetcher=fetch_content,
    )


@celery_app.task(name="forge.ingestion.discover_all")
def discover_all(trigger: str = "scheduled") -> dict[str, int]:
    return asyncio.run(_discover_all(trigger))


async def _discover_all(trigger: str) -> dict[str, int]:
    user_id = DEFAULT_USER_ID
    async with session_scope() as session:
        service = _service(session)
        run = await service.start_run(user_id, trigger)
        run_id = run.id
        sources = await SqlSourcesRepository(session).list_enabled_sources(user_id)
        source_ids = [s.id for s in sources]

    new_article_ids: list[UUID] = []
    for source_id in source_ids:
        # One transaction per source: a failing source never rolls back others.
        async with session_scope() as session:
            service = _service(session)
            new_article_ids.extend(await service.discover_source(user_id, source_id, run_id))

    async with session_scope() as session:
        await _service(session).finish_run(user_id, run_id)

    for article_id in new_article_ids:
        fetch_article.apply_async(args=[str(article_id)], queue="ingestion")
    return {"sources": len(source_ids), "new_articles": len(new_article_ids)}


@celery_app.task(
    name="forge.ingestion.fetch_article",
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_kwargs={"max_retries": 3},
)
def fetch_article(article_id: str) -> None:
    asyncio.run(_fetch_article(UUID(article_id)))


async def _fetch_article(article_id: UUID) -> None:
    async with session_scope() as session:
        await _service(session).fetch_article(DEFAULT_USER_ID, article_id)
