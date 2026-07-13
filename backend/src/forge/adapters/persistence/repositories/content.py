from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from forge.adapters.persistence.models.content import Article, DiscoveryRun
from forge.domain.content import ArticleStatus


class SqlContentRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_article(self, user_id: UUID, article_id: UUID) -> Article | None:
        stmt = select(Article).where(Article.user_id == user_id, Article.id == article_id)
        result: Article | None = await self._session.scalar(stmt)
        return result

    async def add_article(self, article: Article) -> Article:
        self._session.add(article)
        await self._session.flush()
        return article

    async def canonical_url_exists(self, user_id: UUID, canonical_url: str) -> bool:
        stmt = select(Article.id).where(
            Article.user_id == user_id, Article.canonical_url == canonical_url
        )
        return (await self._session.scalar(stmt)) is not None

    async def content_hash_exists(self, user_id: UUID, content_hash: str) -> bool:
        stmt = select(Article.id).where(
            Article.user_id == user_id, Article.content_hash == content_hash
        )
        return (await self._session.scalar(stmt)) is not None

    async def list_by_status(
        self, user_id: UUID, status: ArticleStatus, limit: int = 100
    ) -> list[Article]:
        stmt = (
            select(Article)
            .where(Article.user_id == user_id, Article.status == status)
            .order_by(Article.created_at.desc())
            .limit(limit)
        )
        return list((await self._session.scalars(stmt)).all())

    async def add_run(self, run: DiscoveryRun) -> DiscoveryRun:
        self._session.add(run)
        await self._session.flush()
        return run

    async def get_run(self, user_id: UUID, run_id: UUID) -> DiscoveryRun | None:
        stmt = select(DiscoveryRun).where(
            DiscoveryRun.user_id == user_id, DiscoveryRun.id == run_id
        )
        result: DiscoveryRun | None = await self._session.scalar(stmt)
        return result

    async def list_runs(self, user_id: UUID, limit: int = 20) -> list[DiscoveryRun]:
        stmt = (
            select(DiscoveryRun)
            .where(DiscoveryRun.user_id == user_id)
            .order_by(DiscoveryRun.started_at.desc())
            .limit(limit)
        )
        return list((await self._session.scalars(stmt)).all())
