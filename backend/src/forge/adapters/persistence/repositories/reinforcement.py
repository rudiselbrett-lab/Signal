from datetime import datetime
from uuid import UUID

from sqlalchemy import distinct, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from forge.adapters.persistence.models.content import Article
from forge.adapters.persistence.models.knowledge import KnowledgeCard
from forge.adapters.persistence.models.reinforcement import (
    ItemStatus,
    ReviewAttempt,
    ReviewItem,
    ReviewSession,
)


class SqlReinforcementRepository:
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

    async def list_items_for_article(self, user_id: UUID, article_id: UUID) -> list[ReviewItem]:
        stmt = select(ReviewItem).where(
            ReviewItem.user_id == user_id, ReviewItem.article_id == article_id
        )
        return list((await self._session.scalars(stmt)).all())

    async def add_items(self, items: list[ReviewItem]) -> None:
        self._session.add_all(items)
        await self._session.flush()

    async def get_item(self, user_id: UUID, item_id: UUID) -> ReviewItem | None:
        stmt = select(ReviewItem).where(ReviewItem.user_id == user_id, ReviewItem.id == item_id)
        result: ReviewItem | None = await self._session.scalar(stmt)
        return result

    async def list_due_items(self, user_id: UUID, now: datetime, limit: int) -> list[ReviewItem]:
        stmt = (
            select(ReviewItem)
            .where(
                ReviewItem.user_id == user_id,
                ReviewItem.status == ItemStatus.ACTIVE,
                ReviewItem.due_at <= now,
            )
            .order_by(ReviewItem.due_at)  # most overdue first
            .limit(limit)
        )
        return list((await self._session.scalars(stmt)).all())

    async def count_due_items(self, user_id: UUID, now: datetime) -> int:
        stmt = select(func.count(ReviewItem.id)).where(
            ReviewItem.user_id == user_id,
            ReviewItem.status == ItemStatus.ACTIVE,
            ReviewItem.due_at <= now,
        )
        return (await self._session.scalar(stmt)) or 0

    async def add_session(self, session: ReviewSession) -> ReviewSession:
        self._session.add(session)
        await self._session.flush()
        return session

    async def get_session(self, user_id: UUID, session_id: UUID) -> ReviewSession | None:
        stmt = select(ReviewSession).where(
            ReviewSession.user_id == user_id, ReviewSession.id == session_id
        )
        result: ReviewSession | None = await self._session.scalar(stmt)
        return result

    async def add_attempt(self, attempt: ReviewAttempt) -> ReviewAttempt:
        self._session.add(attempt)
        await self._session.flush()
        return attempt

    async def articles_with_due_items(self, user_id: UUID, now: datetime) -> list[UUID]:
        stmt = select(distinct(ReviewItem.article_id)).where(
            ReviewItem.user_id == user_id,
            ReviewItem.status == ItemStatus.ACTIVE,
            ReviewItem.due_at <= now,
        )
        return list((await self._session.scalars(stmt)).all())
