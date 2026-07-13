import uuid
from datetime import datetime
from typing import Any

from pgvector.sqlalchemy import Vector
from sqlalchemy import ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from forge.adapters.persistence.base import Base, ForgeTableMixin, str_enum
from forge.adapters.persistence.models.sources import Source
from forge.config import get_settings
from forge.domain.content import ArticleStatus, EnrichmentStatus

EMBEDDING_DIM = get_settings().embedding_dimensions


class Article(ForgeTableMixin, Base):
    __tablename__ = "articles"
    __table_args__ = (UniqueConstraint("user_id", "canonical_url"),)

    source_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("sources.id", ondelete="SET NULL"), nullable=True
    )
    url: Mapped[str] = mapped_column(Text)
    canonical_url: Mapped[str] = mapped_column(Text)
    external_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    title: Mapped[str] = mapped_column(Text)
    author: Mapped[str | None] = mapped_column(Text, nullable=True)
    published_at: Mapped[datetime | None] = mapped_column(nullable=True)
    fetched_at: Mapped[datetime | None] = mapped_column(nullable=True)

    teaser: Mapped[str | None] = mapped_column(Text, nullable=True)  # feed-provided summary
    full_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    word_count: Mapped[int] = mapped_column(Integer, default=0)
    reading_time_minutes: Mapped[int] = mapped_column(Integer, default=0)
    language: Mapped[str | None] = mapped_column(String(10), nullable=True)
    content_hash: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    item_metadata: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)

    embedding: Mapped[list[float] | None] = mapped_column(
        Vector(EMBEDDING_DIM), nullable=True
    )  # whole-article: title + summary + key ideas
    embedding_version: Mapped[str | None] = mapped_column(String(20), nullable=True)

    status: Mapped[ArticleStatus] = mapped_column(
        str_enum(ArticleStatus), default=ArticleStatus.DISCOVERED, index=True
    )
    enrichment_status: Mapped[EnrichmentStatus] = mapped_column(
        str_enum(EnrichmentStatus), default=EnrichmentStatus.PENDING
    )
    enrichment_error: Mapped[str | None] = mapped_column(Text, nullable=True)

    source: Mapped[Source | None] = relationship()


class DiscoveryRun(ForgeTableMixin, Base):
    __tablename__ = "discovery_runs"

    started_at: Mapped[datetime] = mapped_column()
    finished_at: Mapped[datetime | None] = mapped_column(nullable=True)
    trigger: Mapped[str] = mapped_column(String(20), default="scheduled")  # scheduled | manual
    sources_checked: Mapped[int] = mapped_column(Integer, default=0)
    items_found: Mapped[int] = mapped_column(Integer, default=0)
    items_new: Mapped[int] = mapped_column(Integer, default=0)
    errors: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, default=list)
