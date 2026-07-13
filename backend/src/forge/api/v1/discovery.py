from datetime import datetime
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel, ConfigDict

from forge.adapters.persistence.repositories.content import SqlContentRepository
from forge.api.deps import CurrentUserId, DbSession

router = APIRouter(prefix="/discovery", tags=["discovery"])


class DiscoveryRunOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    started_at: datetime
    finished_at: datetime | None
    trigger: str
    sources_checked: int
    items_found: int
    items_new: int
    errors: list[dict[str, Any]]


def get_content_repo(db: DbSession) -> SqlContentRepository:
    return SqlContentRepository(db)


Repo = Annotated[SqlContentRepository, Depends(get_content_repo)]


@router.post("/run", status_code=status.HTTP_202_ACCEPTED)
async def trigger_discovery(user_id: CurrentUserId) -> dict[str, str]:
    """Enqueue a manual discovery run ("Discover now")."""
    from forge.workers.celery_app import celery_app

    celery_app.send_task(
        "forge.ingestion.discover_all", kwargs={"trigger": "manual"}, queue="ingestion"
    )
    return {"status": "queued"}


@router.get("/runs", response_model=list[DiscoveryRunOut])
async def list_runs(repo: Repo, user_id: CurrentUserId) -> list[DiscoveryRunOut]:
    return [DiscoveryRunOut.model_validate(r) for r in await repo.list_runs(user_id)]
