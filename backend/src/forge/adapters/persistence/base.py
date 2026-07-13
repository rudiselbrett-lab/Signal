"""Declarative base and shared column mixins.

Every Forge table carries: UUID primary key, user_id (multi-user-ready
schema from day one), and created/updated timestamps.
"""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, MetaData, func
from sqlalchemy import Enum as SAEnum
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def str_enum(enum_cls: type, length: int = 32) -> SAEnum:
    """VARCHAR-backed enum: no PG enum types to migrate when values change."""
    return SAEnum(
        enum_cls, native_enum=False, length=length, values_callable=lambda e: [m.value for m in e]
    )


# Explicit naming conventions so Alembic migrations are deterministic.
NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING_CONVENTION)
    # All datetimes are timestamptz; naive timestamps are a bug by construction.
    type_annotation_map = {datetime: DateTime(timezone=True)}  # noqa: RUF012


class ForgeTableMixin:
    id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), index=True)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now(), onupdate=func.now())
