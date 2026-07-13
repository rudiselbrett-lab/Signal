from uuid import UUID

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from forge.adapters.persistence.models.content import Article
from forge.adapters.persistence.models.knowledge import ArticleEntity, Entity, KnowledgeCard
from forge.domain.knowledge import EntityKind


class SqlKnowledgeRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_article(self, user_id: UUID, article_id: UUID) -> Article | None:
        stmt = select(Article).where(Article.user_id == user_id, Article.id == article_id)
        result: Article | None = await self._session.scalar(stmt)
        return result

    async def get_card(self, user_id: UUID, article_id: UUID) -> KnowledgeCard | None:
        stmt = select(KnowledgeCard).where(
            KnowledgeCard.user_id == user_id, KnowledgeCard.article_id == article_id
        )
        result: KnowledgeCard | None = await self._session.scalar(stmt)
        return result

    async def add_card(self, card: KnowledgeCard) -> KnowledgeCard:
        self._session.add(card)
        await self._session.flush()
        return card

    async def get_or_create_entity(
        self, user_id: UUID, kind: EntityKind, name: str, normalized_name: str
    ) -> Entity:
        stmt = select(Entity).where(
            Entity.user_id == user_id,
            Entity.kind == kind,
            Entity.normalized_name == normalized_name,
        )
        entity: Entity | None = await self._session.scalar(stmt)
        if entity is None:
            entity = Entity(user_id=user_id, kind=kind, name=name, normalized_name=normalized_name)
            self._session.add(entity)
            await self._session.flush()
        return entity

    async def link_entity(
        self, user_id: UUID, article_id: UUID, entity_id: UUID, salience: float
    ) -> ArticleEntity:
        stmt = (
            pg_insert(ArticleEntity)
            .values(user_id=user_id, article_id=article_id, entity_id=entity_id, salience=salience)
            .on_conflict_do_nothing(index_elements=["article_id", "entity_id"])
        )
        await self._session.execute(stmt)
        link_stmt = select(ArticleEntity).where(
            ArticleEntity.article_id == article_id, ArticleEntity.entity_id == entity_id
        )
        link: ArticleEntity | None = await self._session.scalar(link_stmt)
        assert link is not None
        return link
