"""Ingestion service: sources → discovered articles with full text.

Flow (each step an independently retryable Celery task):
  discover_all ──▶ discover_source (per enabled source) ──▶ fetch_article
                                                              └─ emits article.discovered
"""

from collections.abc import Callable
from datetime import UTC, datetime
from typing import Protocol
from uuid import UUID

import structlog

from forge.adapters.persistence.models.content import Article, DiscoveryRun
from forge.adapters.persistence.models.sources import Source
from forge.adapters.sources.base import SourceAdapter
from forge.domain.content import (
    ArticleStatus,
    EnrichmentStatus,
    canonicalize_url,
    content_fingerprint,
    estimate_reading_time,
)
from forge.domain.sources import RawItem, SourceStatus
from forge.events import publish
from forge.events.catalog import ArticleDiscovered
from forge.services.ingestion.fetcher import FetchedContent
from forge.services.sources.ports import SourcesRepository

logger = structlog.get_logger(__name__)

MAX_FAILURES_BEFORE_ERRORING = 5


class ContentRepository(Protocol):
    async def get_article(self, user_id: UUID, article_id: UUID) -> Article | None: ...
    async def add_article(self, article: Article) -> Article: ...
    async def canonical_url_exists(self, user_id: UUID, canonical_url: str) -> bool: ...
    async def content_hash_exists(self, user_id: UUID, content_hash: str) -> bool: ...
    async def add_run(self, run: DiscoveryRun) -> DiscoveryRun: ...
    async def get_run(self, user_id: UUID, run_id: UUID) -> DiscoveryRun | None: ...
    async def list_runs(self, user_id: UUID, limit: int = 20) -> list[DiscoveryRun]: ...


class Fetcher(Protocol):
    async def __call__(self, url: str) -> FetchedContent: ...


class IngestionService:
    def __init__(
        self,
        content_repo: ContentRepository,
        sources_repo: SourcesRepository,
        adapter_for: Callable[[str], SourceAdapter],
        fetcher: Fetcher,
    ) -> None:
        self._content = content_repo
        self._sources = sources_repo
        self._adapter_for = adapter_for
        self._fetch = fetcher

    async def start_run(self, user_id: UUID, trigger: str) -> DiscoveryRun:
        run = DiscoveryRun(user_id=user_id, started_at=datetime.now(UTC), trigger=trigger)
        return await self._content.add_run(run)

    async def discover_source(self, user_id: UUID, source_id: UUID, run_id: UUID) -> list[UUID]:
        """Check one source; returns ids of newly created articles. Never raises
        on adapter failure — failures are recorded on the source and the run."""
        source = await self._sources.get_source(user_id, source_id)
        run = await self._content.get_run(user_id, run_id)
        if source is None or run is None or not source.enabled:
            return []
        log = logger.bind(source=source.name, source_type=str(source.source_type))
        run.sources_checked += 1
        try:
            adapter = self._adapter_for(source.source_type)
            items = await adapter.fetch_new_items(source, since=source.last_success_at)
        except Exception as exc:
            self._record_failure(source, run, exc)
            log.warning("discovery.source_failed", error=str(exc))
            return []

        source.last_checked_at = datetime.now(UTC)
        source.last_success_at = source.last_checked_at
        source.failure_count = 0
        if source.status == SourceStatus.ERRORING:
            source.status = SourceStatus.ACTIVE

        run.items_found += len(items)
        new_ids: list[UUID] = []
        for item in items:
            article = await self._ingest_item(user_id, source, item)
            if article is not None:
                new_ids.append(article.id)
        run.items_new += len(new_ids)
        log.info("discovery.source_done", found=len(items), new=len(new_ids))
        return new_ids

    async def _ingest_item(self, user_id: UUID, source: Source, item: RawItem) -> Article | None:
        canonical = canonicalize_url(item.url)
        if await self._content.canonical_url_exists(user_id, canonical):
            return None
        article = Article(
            user_id=user_id,
            source_id=source.id,
            url=item.url,
            canonical_url=canonical,
            external_id=item.external_id,
            title=item.title,
            author=item.author,
            published_at=item.published_at,
            teaser=item.summary,
            item_metadata=item.metadata,
            status=ArticleStatus.DISCOVERED,
            enrichment_status=EnrichmentStatus.PENDING,
        )
        return await self._content.add_article(article)

    async def fetch_article(self, user_id: UUID, article_id: UUID) -> Article | None:
        """Fill in full text. On success emits article.discovered for scoring."""
        article = await self._content.get_article(user_id, article_id)
        if article is None or article.full_text:
            return article
        try:
            content = await self._fetch(article.url)
        except Exception as exc:
            article.enrichment_status = EnrichmentStatus.FAILED
            article.enrichment_error = str(exc)
            # Teaser-only articles are still usable if the source provided one.
            if article.teaser:
                article.full_text = article.teaser
                self._finalize_text(article)
            logger.warning("ingestion.fetch_failed", url=article.url, error=str(exc))
            return article

        article.full_text = content.text
        article.fetched_at = datetime.now(UTC)
        article.language = content.language
        if content.title and article.title == article.url:
            article.title = content.title
        article.author = article.author or content.author
        article.published_at = article.published_at or content.published_at
        self._finalize_text(article)

        fingerprint = content_fingerprint(content.text)
        if await self._content.content_hash_exists(user_id, fingerprint):
            # Same content already ingested under a different URL.
            article.status = ArticleStatus.ARCHIVED
            article.enrichment_status = EnrichmentStatus.FETCHED
            return article
        article.content_hash = fingerprint
        article.enrichment_status = EnrichmentStatus.FETCHED
        publish(ArticleDiscovered(article_id=str(article.id), user_id=str(user_id)))
        return article

    def _finalize_text(self, article: Article) -> None:
        words = len((article.full_text or "").split())
        article.word_count = words
        article.reading_time_minutes = estimate_reading_time(words)

    def _record_failure(self, source: Source, run: DiscoveryRun, exc: Exception) -> None:
        source.last_checked_at = datetime.now(UTC)
        source.failure_count += 1
        if source.failure_count >= MAX_FAILURES_BEFORE_ERRORING:
            source.status = SourceStatus.ERRORING
        run.errors = [*run.errors, {"source": source.name, "error": str(exc)}]

    async def finish_run(self, user_id: UUID, run_id: UUID) -> None:
        run = await self._content.get_run(user_id, run_id)
        if run is not None:
            run.finished_at = datetime.now(UTC)
