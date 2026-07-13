"""Library service: the user's knowledge library and article lifecycle."""

from typing import Protocol
from uuid import UUID

from forge.adapters.persistence.models.content import Article
from forge.adapters.persistence.models.knowledge import Entity, KnowledgeCard
from forge.adapters.persistence.models.scoring import ArticleScore
from forge.api.errors import ConflictError, NotFoundError
from forge.domain.content import ArticleStatus
from forge.domain.content.transitions import InvalidTransition, apply_action
from forge.events import publish
from forge.events.catalog import ArticleRead, ArticleSaved, SuggestionDismissed


class LibraryRepository(Protocol):
    async def get_article(self, user_id: UUID, article_id: UUID) -> Article | None: ...
    async def list_articles(
        self,
        user_id: UUID,
        statuses: list[ArticleStatus] | None,
        order_by_score: bool,
        limit: int,
        offset: int,
    ) -> list[tuple[Article, ArticleScore | None, KnowledgeCard | None]]: ...
    async def get_score(self, user_id: UUID, article_id: UUID) -> ArticleScore | None: ...
    async def get_card(self, user_id: UUID, article_id: UUID) -> KnowledgeCard | None: ...
    async def get_entities(self, user_id: UUID, article_id: UUID) -> list[Entity]: ...


class LibraryService:
    def __init__(self, repo: LibraryRepository) -> None:
        self._repo = repo

    async def list_articles(
        self,
        user_id: UUID,
        statuses: list[ArticleStatus] | None = None,
        order_by_score: bool = False,
        limit: int = 50,
        offset: int = 0,
    ) -> list[tuple[Article, ArticleScore | None, KnowledgeCard | None]]:
        return await self._repo.list_articles(user_id, statuses, order_by_score, limit, offset)

    async def get_detail(
        self, user_id: UUID, article_id: UUID
    ) -> tuple[Article, ArticleScore | None, KnowledgeCard | None, list[Entity]]:
        article = await self._get_or_404(user_id, article_id)
        return (
            article,
            await self._repo.get_score(user_id, article_id),
            await self._repo.get_card(user_id, article_id),
            await self._repo.get_entities(user_id, article_id),
        )

    async def apply_action(self, user_id: UUID, article_id: UUID, action: str) -> Article:
        article = await self._get_or_404(user_id, article_id)
        previous = article.status
        try:
            article.status = apply_action(action, previous)
        except InvalidTransition as exc:
            raise ConflictError(str(exc)) from exc
        if article.status == previous:
            return article  # idempotent re-application: no duplicate events

        ids = {"article_id": str(article.id), "user_id": str(user_id)}
        if action == "save":
            publish(ArticleSaved(**ids))
        elif action == "mark_read":
            # Reading straight from the feed implies saving: enrichment must
            # still happen for the reinforcement engine to have key ideas.
            if previous in (ArticleStatus.DISCOVERED, ArticleStatus.SUGGESTED):
                publish(ArticleSaved(**ids))
            publish(ArticleRead(**ids))
        elif action == "dismiss":
            publish(SuggestionDismissed(**ids))
        return article

    async def _get_or_404(self, user_id: UUID, article_id: UUID) -> Article:
        article = await self._repo.get_article(user_id, article_id)
        if article is None:
            raise NotFoundError("article not found")
        return article
