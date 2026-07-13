from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from forge.adapters.persistence.models.content import Article
from forge.adapters.persistence.models.knowledge import ArticleEntity, Entity, KnowledgeCard
from forge.adapters.persistence.models.scoring import ArticleScore
from forge.domain.content import ArticleStatus


class SqlLibraryRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_article(self, user_id: UUID, article_id: UUID) -> Article | None:
        stmt = (
            select(Article)
            .options(joinedload(Article.source))
            .where(Article.user_id == user_id, Article.id == article_id)
        )
        result: Article | None = await self._session.scalar(stmt)
        return result

    async def list_articles(
        self,
        user_id: UUID,
        statuses: list[ArticleStatus] | None,
        order_by_score: bool,
        limit: int,
        offset: int,
    ) -> list[tuple[Article, ArticleScore | None, KnowledgeCard | None]]:
        stmt = (
            select(Article, ArticleScore, KnowledgeCard)
            .options(joinedload(Article.source))
            .outerjoin(ArticleScore, ArticleScore.article_id == Article.id)
            .outerjoin(KnowledgeCard, KnowledgeCard.article_id == Article.id)
            .where(Article.user_id == user_id)
        )
        if statuses:
            stmt = stmt.where(Article.status.in_(statuses))
        if order_by_score:
            stmt = stmt.order_by(ArticleScore.overall.desc().nulls_last())
        else:
            stmt = stmt.order_by(Article.created_at.desc())
        stmt = stmt.limit(limit).offset(offset)
        rows = (await self._session.execute(stmt)).unique().all()
        return [(row[0], row[1], row[2]) for row in rows]

    async def get_score(self, user_id: UUID, article_id: UUID) -> ArticleScore | None:
        stmt = select(ArticleScore).where(
            ArticleScore.user_id == user_id, ArticleScore.article_id == article_id
        )
        result: ArticleScore | None = await self._session.scalar(stmt)
        return result

    async def get_card(self, user_id: UUID, article_id: UUID) -> KnowledgeCard | None:
        stmt = select(KnowledgeCard).where(
            KnowledgeCard.user_id == user_id, KnowledgeCard.article_id == article_id
        )
        result: KnowledgeCard | None = await self._session.scalar(stmt)
        return result

    async def get_entities(self, user_id: UUID, article_id: UUID) -> list[Entity]:
        stmt = (
            select(Entity)
            .join(ArticleEntity, ArticleEntity.entity_id == Entity.id)
            .where(ArticleEntity.article_id == article_id, Entity.user_id == user_id)
            .order_by(ArticleEntity.salience.desc(), Entity.name)
        )
        return list((await self._session.scalars(stmt)).all())
