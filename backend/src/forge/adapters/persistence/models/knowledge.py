import uuid
from typing import Any

from sqlalchemy import Float, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from forge.adapters.persistence.base import Base, ForgeTableMixin, str_enum
from forge.domain.knowledge import EntityKind
from forge.domain.scoring import Difficulty


class KnowledgeCard(ForgeTableMixin, Base):
    __tablename__ = "knowledge_cards"

    article_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("articles.id", ondelete="CASCADE"), unique=True
    )
    summary: Mapped[str] = mapped_column(Text)
    key_ideas: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, default=list)  # {idea, quote}
    mental_models: Mapped[list[str]] = mapped_column(JSONB, default=list)
    frameworks: Mapped[list[str]] = mapped_column(JSONB, default=list)
    topics: Mapped[list[str]] = mapped_column(ARRAY(Text), default=list)
    tags: Mapped[list[str]] = mapped_column(ARRAY(Text), default=list)
    difficulty: Mapped[Difficulty] = mapped_column(str_enum(Difficulty))
    extraction_version: Mapped[str] = mapped_column(String(10))


class Entity(ForgeTableMixin, Base):
    __tablename__ = "entities"
    __table_args__ = (UniqueConstraint("user_id", "kind", "normalized_name"),)

    name: Mapped[str] = mapped_column(String(200))
    kind: Mapped[EntityKind] = mapped_column(str_enum(EntityKind))
    normalized_name: Mapped[str] = mapped_column(String(200))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)


class ArticleEntity(ForgeTableMixin, Base):
    __tablename__ = "article_entities"
    __table_args__ = (UniqueConstraint("article_id", "entity_id"),)

    article_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("articles.id", ondelete="CASCADE"), index=True
    )
    entity_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("entities.id", ondelete="CASCADE"), index=True
    )
    salience: Mapped[float] = mapped_column(Float, default=1.0)
