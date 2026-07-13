"""Request/response DTOs for the Sources context."""

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from forge.domain.sources import SourceStatus, SourceType


class CategoryCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    color: str = "#7c6cf5"
    priority_weight: float = Field(default=1.0, ge=0.1, le=5.0)


class CategoryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    color: str
    priority_weight: float


class SourceCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    source_type: SourceType
    config: dict[str, Any]
    category_id: UUID | None = None
    priority_weight: float = Field(default=1.0, ge=0.1, le=5.0)
    enabled: bool = True


class SourceUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    config: dict[str, Any] | None = None
    category_id: UUID | None = None
    priority_weight: float | None = Field(default=None, ge=0.1, le=5.0)
    enabled: bool | None = None


class SourceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    source_type: SourceType
    config: dict[str, Any]
    category_id: UUID | None
    priority_weight: float
    enabled: bool
    status: SourceStatus
    failure_count: int
    last_checked_at: datetime | None
    last_success_at: datetime | None


class SourcePreset(BaseModel):
    """A one-click addable source."""

    name: str
    source_type: SourceType
    config: dict[str, Any]
    description: str
