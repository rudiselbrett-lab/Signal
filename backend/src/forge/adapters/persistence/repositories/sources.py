from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from forge.adapters.persistence.models.sources import Category, Source


class SqlSourcesRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_sources(self, user_id: UUID) -> list[Source]:
        stmt = select(Source).where(Source.user_id == user_id).order_by(Source.created_at)
        return list((await self._session.scalars(stmt)).all())

    async def get_source(self, user_id: UUID, source_id: UUID) -> Source | None:
        stmt = select(Source).where(Source.user_id == user_id, Source.id == source_id)
        result: Source | None = await self._session.scalar(stmt)
        return result

    async def add_source(self, source: Source) -> Source:
        self._session.add(source)
        await self._session.flush()
        return source

    async def delete_source(self, source: Source) -> None:
        await self._session.delete(source)

    async def list_enabled_sources(self, user_id: UUID) -> list[Source]:
        stmt = select(Source).where(Source.user_id == user_id, Source.enabled.is_(True))
        return list((await self._session.scalars(stmt)).all())

    async def list_categories(self, user_id: UUID) -> list[Category]:
        stmt = select(Category).where(Category.user_id == user_id).order_by(Category.name)
        return list((await self._session.scalars(stmt)).all())

    async def get_category(self, user_id: UUID, category_id: UUID) -> Category | None:
        stmt = select(Category).where(Category.user_id == user_id, Category.id == category_id)
        result: Category | None = await self._session.scalar(stmt)
        return result

    async def add_category(self, category: Category) -> Category:
        self._session.add(category)
        await self._session.flush()
        return category

    async def delete_category(self, category: Category) -> None:
        await self._session.delete(category)

    async def category_name_exists(self, user_id: UUID, name: str) -> bool:
        stmt = select(Category.id).where(Category.user_id == user_id, Category.name == name)
        return (await self._session.scalar(stmt)) is not None
