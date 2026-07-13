import uuid

from pgvector.sqlalchemy import Vector
from sqlalchemy import Computed, ForeignKey, Integer, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import TSVECTOR
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from forge.adapters.persistence.base import Base, ForgeTableMixin
from forge.config import get_settings

EMBEDDING_DIM = get_settings().embedding_dimensions


class ArticleChunk(ForgeTableMixin, Base):
    __tablename__ = "article_chunks"
    __table_args__ = (UniqueConstraint("article_id", "chunk_index"),)

    article_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("articles.id", ondelete="CASCADE"), index=True
    )
    chunk_index: Mapped[int] = mapped_column(Integer)
    text: Mapped[str] = mapped_column(Text)
    token_count: Mapped[int] = mapped_column(Integer, default=0)
    embedding: Mapped[list[float] | None] = mapped_column(Vector(EMBEDDING_DIM), nullable=True)
    tsv: Mapped[str | None] = mapped_column(
        TSVECTOR,
        Computed("to_tsvector('english', text)", persisted=True),
        nullable=True,
    )
