from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from forge.adapters.persistence.models.content import Article
from forge.adapters.persistence.models.scoring import ArticleScore
from forge.adapters.persistence.models.sources import Category


class SqlScoringRepository:
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

    async def get_score(self, user_id: UUID, article_id: UUID) -> ArticleScore | None:
        stmt = select(ArticleScore).where(
            ArticleScore.user_id == user_id, ArticleScore.article_id == article_id
        )
        result: ArticleScore | None = await self._session.scalar(stmt)
        return result

    async def upsert_score(self, score: ArticleScore) -> ArticleScore:
        self._session.add(score)
        await self._session.flush()
        return score

    async def source_weights(self, article: Article) -> tuple[float, float]:
        if article.source is None:
            return 1.0, 1.0
        category_weight = 1.0
        if article.source.category_id is not None:
            category = await self._session.get(Category, article.source.category_id)
            if category is not None:
                category_weight = category.priority_weight
        return article.source.priority_weight, category_weight
