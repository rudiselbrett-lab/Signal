from datetime import UTC, datetime

import pytest

from forge.config import DEFAULT_USER_ID
from forge.domain.content import ArticleStatus, EnrichmentStatus
from forge.domain.sources import RawItem, SourceStatus, SourceType
from forge.events import bus
from forge.services.ingestion.fetcher import ContentFetchError, FetchedContent
from forge.services.ingestion.service import IngestionService
from forge.services.sources.schemas import SourceCreate
from forge.services.sources.service import SourcesService
from tests.fakes import FakeContentRepository, FakeSourcesRepository

USER = DEFAULT_USER_ID


class FakeAdapter:
    source_type = SourceType.RSS

    def __init__(self, items=None, error=None):
        self.items = items or []
        self.error = error

    async def fetch_new_items(self, source, since):
        if self.error:
            raise self.error
        return self.items


def make_items(n=2):
    return [
        RawItem(
            external_id=f"id-{i}",
            url=f"https://example.com/post-{i}?utm_source=feed",
            title=f"Post {i}",
            published_at=datetime(2026, 7, 1, tzinfo=UTC),
        )
        for i in range(n)
    ]


@pytest.fixture(autouse=True)
def clean_bus():
    bus.clear_subscribers()
    yield
    bus.clear_subscribers()


@pytest.fixture
async def env():
    sources_repo = FakeSourcesRepository()
    content_repo = FakeContentRepository()
    svc = SourcesService(sources_repo)
    source = await svc.create_source(
        USER,
        SourceCreate(
            name="Feed",
            source_type=SourceType.RSS,
            config={"feed_url": "https://example.com/feed.xml"},
        ),
    )
    return sources_repo, content_repo, source


def make_service(sources_repo, content_repo, adapter, fetcher=None):
    async def default_fetcher(url):
        return FetchedContent(text="word " * 500, title="Fetched Title", language="en")

    return IngestionService(
        content_repo=content_repo,
        sources_repo=sources_repo,
        adapter_for=lambda st: adapter,
        fetcher=fetcher or default_fetcher,
    )


async def test_discovery_creates_articles_and_dedupes(env):
    sources_repo, content_repo, source = env
    service = make_service(sources_repo, content_repo, FakeAdapter(items=make_items(2)))
    run = await service.start_run(USER, "manual")

    new_ids = await service.discover_source(USER, source.id, run.id)
    assert len(new_ids) == 2
    # Second run: same items, all deduped by canonical URL.
    assert await service.discover_source(USER, source.id, run.id) == []

    run = await content_repo.get_run(USER, run.id)
    assert run.items_found == 4
    assert run.items_new == 2
    article = await content_repo.get_article(USER, new_ids[0])
    assert article.canonical_url == "https://example.com/post-0"
    assert article.status == ArticleStatus.DISCOVERED


async def test_source_failure_is_recorded_not_raised(env):
    sources_repo, content_repo, source = env
    service = make_service(sources_repo, content_repo, FakeAdapter(error=RuntimeError("feed down")))
    run = await service.start_run(USER, "scheduled")

    for _ in range(5):
        assert await service.discover_source(USER, source.id, run.id) == []

    assert source.failure_count == 5
    assert source.status == SourceStatus.ERRORING
    run = await content_repo.get_run(USER, run.id)
    assert len(run.errors) == 5


async def test_fetch_article_fills_text_and_emits_event(env):
    sources_repo, content_repo, source = env
    service = make_service(sources_repo, content_repo, FakeAdapter(items=make_items(1)))
    run = await service.start_run(USER, "manual")
    [article_id] = await service.discover_source(USER, source.id, run.id)

    seen = []
    bus.subscribe("article.discovered", seen.append)
    article = await service.fetch_article(USER, article_id)

    assert article.enrichment_status == EnrichmentStatus.FETCHED
    assert article.word_count == 500
    assert article.reading_time_minutes == 3
    assert len(seen) == 1
    assert seen[0].payload() == {"article_id": str(article_id), "user_id": str(USER)}


async def test_fetch_failure_marks_failed_and_keeps_teaser(env):
    sources_repo, content_repo, source = env

    async def failing_fetcher(url):
        raise ContentFetchError("boom")

    items = make_items(1)
    items[0] = items[0].model_copy(update={"summary": "teaser text here"})
    service = make_service(sources_repo, content_repo, FakeAdapter(items=items), failing_fetcher)
    run = await service.start_run(USER, "manual")
    [article_id] = await service.discover_source(USER, source.id, run.id)

    article = await service.fetch_article(USER, article_id)
    assert article.enrichment_status == EnrichmentStatus.FAILED
    assert article.full_text == "teaser text here"


async def test_duplicate_content_across_sources_is_archived(env):
    sources_repo, content_repo, source = env
    service = make_service(sources_repo, content_repo, FakeAdapter(items=make_items(2)))
    run = await service.start_run(USER, "manual")
    ids = await service.discover_source(USER, source.id, run.id)

    first = await service.fetch_article(USER, ids[0])
    second = await service.fetch_article(USER, ids[1])  # identical fetched text

    assert first.status == ArticleStatus.DISCOVERED
    assert second.status == ArticleStatus.ARCHIVED
    assert second.content_hash is None
