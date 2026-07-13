from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, status

from forge.adapters.persistence.repositories.sources import SqlSourcesRepository
from forge.api.deps import CurrentUserId, DbSession
from forge.services.sources.presets import PRESETS
from forge.services.sources.schemas import (
    CategoryCreate,
    CategoryOut,
    SourceCreate,
    SourceOut,
    SourcePreset,
    SourceUpdate,
)
from forge.services.sources.service import SourcesService

router = APIRouter(prefix="/sources", tags=["sources"])


def get_sources_service(db: DbSession) -> SourcesService:
    return SourcesService(SqlSourcesRepository(db))


Service = Annotated[SourcesService, Depends(get_sources_service)]


@router.get("", response_model=list[SourceOut])
async def list_sources(svc: Service, user_id: CurrentUserId) -> list[SourceOut]:
    return [SourceOut.model_validate(s) for s in await svc.list_sources(user_id)]


@router.post("", response_model=SourceOut, status_code=status.HTTP_201_CREATED)
async def create_source(data: SourceCreate, svc: Service, user_id: CurrentUserId) -> SourceOut:
    return SourceOut.model_validate(await svc.create_source(user_id, data))


@router.patch("/{source_id}", response_model=SourceOut)
async def update_source(
    source_id: UUID, data: SourceUpdate, svc: Service, user_id: CurrentUserId
) -> SourceOut:
    return SourceOut.model_validate(await svc.update_source(user_id, source_id, data))


@router.delete("/{source_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_source(source_id: UUID, svc: Service, user_id: CurrentUserId) -> None:
    await svc.delete_source(user_id, source_id)


@router.get("/presets", response_model=list[SourcePreset])
async def list_presets() -> list[SourcePreset]:
    return PRESETS


categories_router = APIRouter(prefix="/categories", tags=["sources"])


@categories_router.get("", response_model=list[CategoryOut])
async def list_categories(svc: Service, user_id: CurrentUserId) -> list[CategoryOut]:
    return [CategoryOut.model_validate(c) for c in await svc.list_categories(user_id)]


@categories_router.post("", response_model=CategoryOut, status_code=status.HTTP_201_CREATED)
async def create_category(
    data: CategoryCreate, svc: Service, user_id: CurrentUserId
) -> CategoryOut:
    return CategoryOut.model_validate(await svc.create_category(user_id, data))


@categories_router.delete("/{category_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_category(category_id: UUID, svc: Service, user_id: CurrentUserId) -> None:
    await svc.delete_category(user_id, category_id)
