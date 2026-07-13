import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import Enum as SAEnum
from sqlalchemy import ForeignKey, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from forge.adapters.persistence.base import Base, ForgeTableMixin
from forge.domain.sources import SourceStatus, SourceType


def _str_enum(enum_cls: type, length: int = 32) -> SAEnum:
    # VARCHAR-backed enums: no PG enum types to migrate when values change.
    return SAEnum(
        enum_cls, native_enum=False, length=length, values_callable=lambda e: [m.value for m in e]
    )


class Category(ForgeTableMixin, Base):
    __tablename__ = "categories"
    __table_args__ = (UniqueConstraint("user_id", "name"),)

    name: Mapped[str] = mapped_column(String(100))
    color: Mapped[str] = mapped_column(String(20), default="#7c6cf5")
    priority_weight: Mapped[float] = mapped_column(default=1.0)

    sources: Mapped[list["Source"]] = relationship(back_populates="category")


class Source(ForgeTableMixin, Base):
    __tablename__ = "sources"

    category_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("categories.id", ondelete="SET NULL"), nullable=True
    )
    name: Mapped[str] = mapped_column(String(200))
    source_type: Mapped[SourceType] = mapped_column(_str_enum(SourceType))
    config: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    enabled: Mapped[bool] = mapped_column(default=True)
    priority_weight: Mapped[float] = mapped_column(default=1.0)
    last_checked_at: Mapped[datetime | None] = mapped_column(nullable=True)
    last_success_at: Mapped[datetime | None] = mapped_column(nullable=True)
    failure_count: Mapped[int] = mapped_column(default=0)
    status: Mapped[SourceStatus] = mapped_column(
        _str_enum(SourceStatus), default=SourceStatus.ACTIVE
    )

    category: Mapped[Category | None] = relationship(back_populates="sources")
