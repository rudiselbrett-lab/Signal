"""In-memory fakes for repository ports; used by service and API tests."""

import uuid
from uuid import UUID

from forge.adapters.persistence.models.sources import Category, Source


class FakeSourcesRepository:
    def __init__(self):
        self.sources: dict[UUID, Source] = {}
        self.categories: dict[UUID, Category] = {}

    async def list_sources(self, user_id: UUID) -> list[Source]:
        return [s for s in self.sources.values() if s.user_id == user_id]

    async def get_source(self, user_id: UUID, source_id: UUID) -> Source | None:
        s = self.sources.get(source_id)
        return s if s and s.user_id == user_id else None

    async def add_source(self, source: Source) -> Source:
        source.id = source.id or uuid.uuid4()
        # Mirror ORM column defaults that only apply on flush.
        if source.status is None:
            source.status = "active"
        if source.failure_count is None:
            source.failure_count = 0
        self.sources[source.id] = source
        return source

    async def delete_source(self, source: Source) -> None:
        self.sources.pop(source.id, None)

    async def list_enabled_sources(self, user_id: UUID) -> list[Source]:
        return [s for s in self.sources.values() if s.user_id == user_id and s.enabled]

    async def list_categories(self, user_id: UUID) -> list[Category]:
        return [c for c in self.categories.values() if c.user_id == user_id]

    async def get_category(self, user_id: UUID, category_id: UUID) -> Category | None:
        c = self.categories.get(category_id)
        return c if c and c.user_id == user_id else None

    async def add_category(self, category: Category) -> Category:
        category.id = category.id or uuid.uuid4()
        self.categories[category.id] = category
        return category

    async def delete_category(self, category: Category) -> None:
        self.categories.pop(category.id, None)

    async def category_name_exists(self, user_id: UUID, name: str) -> bool:
        return any(c.user_id == user_id and c.name == name for c in self.categories.values())


class FakeContentRepository:
    def __init__(self):
        self.articles = {}
        self.runs = {}

    async def get_article(self, user_id, article_id):
        a = self.articles.get(article_id)
        return a if a and a.user_id == user_id else None

    async def add_article(self, article):
        article.id = article.id or uuid.uuid4()
        if article.item_metadata is None:
            article.item_metadata = {}
        if article.word_count is None:
            article.word_count = 0
        self.articles[article.id] = article
        return article

    async def canonical_url_exists(self, user_id, canonical_url):
        return any(
            a.user_id == user_id and a.canonical_url == canonical_url
            for a in self.articles.values()
        )

    async def content_hash_exists(self, user_id, content_hash):
        return any(
            a.user_id == user_id and a.content_hash == content_hash for a in self.articles.values()
        )

    async def add_run(self, run):
        run.id = run.id or uuid.uuid4()
        run.sources_checked = run.sources_checked or 0
        run.items_found = run.items_found or 0
        run.items_new = run.items_new or 0
        run.errors = run.errors or []
        self.runs[run.id] = run
        return run

    async def get_run(self, user_id, run_id):
        r = self.runs.get(run_id)
        return r if r and r.user_id == user_id else None

    async def list_runs(self, user_id, limit=20):
        return sorted(
            (r for r in self.runs.values() if r.user_id == user_id),
            key=lambda r: r.started_at,
            reverse=True,
        )[:limit]
