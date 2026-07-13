from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

from forge.adapters.embeddings import OpenAIEmbedder
from forge.adapters.persistence.repositories.search import SqlSearchRepository
from forge.api.deps import CurrentUserId, DbSession
from forge.services.search.service import SearchService

router = APIRouter(prefix="/search", tags=["search"])


class SearchHitOut(BaseModel):
    chunk_id: UUID
    article_id: UUID
    chunk_index: int
    chunk_text: str
    score: float
    article_title: str
    article_url: str


def get_search_service(db: DbSession) -> SearchService:
    return SearchService(SqlSearchRepository(db), OpenAIEmbedder())


Service = Annotated[SearchService, Depends(get_search_service)]


@router.get("", response_model=list[SearchHitOut])
async def search(
    svc: Service,
    user_id: CurrentUserId,
    q: Annotated[str, Query(min_length=1, max_length=500)],
    limit: int = Query(default=12, le=50),
) -> list[SearchHitOut]:
    hits = await svc.search(user_id, q, limit=limit)
    return [SearchHitOut(**hit.__dict__) for hit in hits]
