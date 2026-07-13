from datetime import datetime
from typing import Annotated, Any, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, ConfigDict

from forge.adapters.persistence.models.content import Article
from forge.adapters.persistence.models.knowledge import KnowledgeCard
from forge.adapters.persistence.models.scoring import ArticleScore
from forge.adapters.persistence.repositories.library import SqlLibraryRepository
from forge.api.deps import CurrentUserId, DbSession
from forge.domain.content import ArticleStatus
from forge.services.library.service import LibraryService

router = APIRouter(prefix="/articles", tags=["library"])


class ScoreOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    overall: int
    relevance: int
    novelty: int
    credibility: int
    practicality: int
    knowledge_gap: int
    reading_time_bonus: int
    difficulty: str
    rationale: dict[str, Any]


class KnowledgeCardOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    summary: str
    key_ideas: list[dict[str, Any]]
    mental_models: list[str]
    frameworks: list[str]
    topics: list[str]
    tags: list[str]
    difficulty: str


class EntityOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    kind: str


class ArticleListItem(BaseModel):
    id: UUID
    title: str
    author: str | None
    source_name: str | None
    url: str
    status: ArticleStatus
    published_at: datetime | None
    reading_time_minutes: int
    teaser: str | None
    summary: str | None
    topics: list[str]
    score: int | None
    difficulty: str | None


class ArticleDetail(ArticleListItem):
    full_text: str | None
    word_count: int
    score_breakdown: ScoreOut | None
    knowledge_card: KnowledgeCardOut | None
    entities: list[EntityOut]


def _list_item(
    article: Article, score: ArticleScore | None, card: KnowledgeCard | None
) -> ArticleListItem:
    return ArticleListItem(
        id=article.id,
        title=article.title,
        author=article.author,
        source_name=article.source.name if article.source else None,
        url=article.url,
        status=article.status,
        published_at=article.published_at,
        reading_time_minutes=article.reading_time_minutes,
        teaser=article.teaser,
        summary=card.summary if card else None,
        topics=card.topics if card else [],
        score=score.overall if score else None,
        difficulty=str(score.difficulty) if score else None,
    )


def get_library_service(db: DbSession) -> LibraryService:
    return LibraryService(SqlLibraryRepository(db))


Service = Annotated[LibraryService, Depends(get_library_service)]

Action = Literal["save", "start_reading", "mark_read", "dismiss", "archive"]


@router.get("", response_model=list[ArticleListItem])
async def list_articles(
    svc: Service,
    user_id: CurrentUserId,
    status: Annotated[list[ArticleStatus] | None, Query()] = None,
    order: Literal["recent", "score"] = "recent",
    limit: int = Query(default=50, le=200),
    offset: int = Query(default=0, ge=0),
) -> list[ArticleListItem]:
    rows = await svc.list_articles(
        user_id, statuses=status, order_by_score=(order == "score"), limit=limit, offset=offset
    )
    return [_list_item(a, s, c) for a, s, c in rows]


@router.get("/{article_id}", response_model=ArticleDetail)
async def get_article(article_id: UUID, svc: Service, user_id: CurrentUserId) -> ArticleDetail:
    article, score, card, entities = await svc.get_detail(user_id, article_id)
    base = _list_item(article, score, card)
    return ArticleDetail(
        **base.model_dump(),
        full_text=article.full_text,
        word_count=article.word_count,
        score_breakdown=ScoreOut.model_validate(score) if score else None,
        knowledge_card=KnowledgeCardOut.model_validate(card) if card else None,
        entities=[EntityOut.model_validate(e) for e in entities],
    )


@router.post("/{article_id}/actions/{action}", response_model=ArticleListItem)
async def apply_action(
    article_id: UUID, action: Action, svc: Service, user_id: CurrentUserId
) -> ArticleListItem:
    article = await svc.apply_action(user_id, article_id, action)
    return _list_item(article, None, None)
