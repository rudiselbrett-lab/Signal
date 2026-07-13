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
