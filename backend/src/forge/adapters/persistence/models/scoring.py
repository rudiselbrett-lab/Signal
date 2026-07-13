import uuid
from typing import Any

from sqlalchemy import ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from forge.adapters.persistence.base import Base, ForgeTableMixin, str_enum
from forge.domain.scoring import Difficulty


class ArticleScore(ForgeTableMixin, Base):
    __tablename__ = "article_scores"

    article_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("articles.id", ondelete="CASCADE"), unique=True
    )
    overall: Mapped[int] = mapped_column(Integer)
    relevance: Mapped[int] = mapped_column(Integer)
    novelty: Mapped[int] = mapped_column(Integer)
    credibility: Mapped[int] = mapped_column(Integer)
    practicality: Mapped[int] = mapped_column(Integer)
    knowledge_gap: Mapped[int] = mapped_column(Integer)
    reading_time_bonus: Mapped[int] = mapped_column(Integer)
    difficulty: Mapped[Difficulty] = mapped_column(str_enum(Difficulty))
    rationale: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    scoring_version: Mapped[str] = mapped_column(String(10))


class LLMCall(ForgeTableMixin, Base):
    """Audit/cost log for every LLM call (spend is a first-class metric)."""

    __tablename__ = "llm_calls"

    prompt_name: Mapped[str] = mapped_column(String(100), index=True)
    model: Mapped[str] = mapped_column(String(100))
    input_tokens: Mapped[int] = mapped_column(Integer, default=0)
    output_tokens: Mapped[int] = mapped_column(Integer, default=0)
    latency_ms: Mapped[int] = mapped_column(Integer, default=0)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
