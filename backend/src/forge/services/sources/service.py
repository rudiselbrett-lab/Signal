"""Sources application service: manage what Forge learns from."""

from uuid import UUID

from pydantic import ValidationError

from forge.adapters.persistence.models.sources import Category, Source
from forge.api.errors import ConflictError, NotFoundError, ValidationFailedError
from forge.domain.sources import SourceStatus, validate_source_config
from forge.services.sources.ports import SourcesRepository
from forge.services.sources.schemas import CategoryCreate, SourceCreate, SourceUpdate


class SourcesService:
    def __init__(self, repo: SourcesRepository) -> None:
        self._repo = repo

    # --- sources -------------------------------------------------------------

    async def list_sources(self, user_id: UUID) -> list[Source]:
        return await self._repo.list_sources(user_id)

    async def create_source(self, user_id: UUID, data: SourceCreate) -> Source:
        try:
            config = validate_source_config(data.source_type, data.config)
        except ValidationError as exc:
            raise ValidationFailedError(f"invalid config for {data.source_type}: {exc}") from exc
        if data.category_id and not await self._repo.get_category(user_id, data.category_id):
            raise NotFoundError("category not found")
        source = Source(
            user_id=user_id,
            name=data.name,
            source_type=data.source_type,
            config=config,
            category_id=data.category_id,
            priority_weight=data.priority_weight,
            enabled=data.enabled,
        )
        return await self._repo.add_source(source)

    async def update_source(self, user_id: UUID, source_id: UUID, data: SourceUpdate) -> Source:
        source = await self._get_source_or_404(user_id, source_id)
        if data.config is not None:
            try:
                source.config = validate_source_config(source.source_type, data.config)
            except ValidationError as exc:
                raise ValidationFailedError(str(exc)) from exc
        if data.name is not None:
            source.name = data.name
        if data.category_id is not None:
            if not await self._repo.get_category(user_id, data.category_id):
                raise NotFoundError("category not found")
            source.category_id = data.category_id
        if data.priority_weight is not None:
            source.priority_weight = data.priority_weight
        if data.enabled is not None:
            source.enabled = data.enabled
            # Re-enabling clears the error state so discovery retries immediately.
            if data.enabled and source.status == SourceStatus.ERRORING:
                source.status = SourceStatus.ACTIVE
                source.failure_count = 0
        return source

    async def delete_source(self, user_id: UUID, source_id: UUID) -> None:
        source = await self._get_source_or_404(user_id, source_id)
        await self._repo.delete_source(source)

    async def _get_source_or_404(self, user_id: UUID, source_id: UUID) -> Source:
        source = await self._repo.get_source(user_id, source_id)
        if source is None:
            raise NotFoundError("source not found")
        return source

    # --- categories ----------------------------------------------------------

    async def list_categories(self, user_id: UUID) -> list[Category]:
        return await self._repo.list_categories(user_id)

    async def create_category(self, user_id: UUID, data: CategoryCreate) -> Category:
        if await self._repo.category_name_exists(user_id, data.name):
            raise ConflictError(f"category {data.name!r} already exists")
        category = Category(
            user_id=user_id,
            name=data.name,
            color=data.color,
            priority_weight=data.priority_weight,
        )
        return await self._repo.add_category(category)

    async def delete_category(self, user_id: UUID, category_id: UUID) -> None:
        category = await self._repo.get_category(user_id, category_id)
        if category is None:
            raise NotFoundError("category not found")
        await self._repo.delete_category(category)
