import uuid
from datetime import datetime
from enum import StrEnum
from typing import Any

from sqlalchemy import Float, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from forge.adapters.persistence.base import Base, ForgeTableMixin, str_enum


class CardType(StrEnum):
    QUICK_RECALL = "quick_recall"
    MULTIPLE_CHOICE = "multiple_choice"
    SCENARIO = "scenario"
    COMPARE = "compare"
    EXPLAIN = "explain"


class ItemStatus(StrEnum):
    ACTIVE = "active"
    SUSPENDED = "suspended"
    RETIRED = "retired"


class ReviewItem(ForgeTableMixin, Base):
    __tablename__ = "review_items"

    article_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("articles.id", ondelete="CASCADE"), index=True
    )
    card_type: Mapped[CardType] = mapped_column(str_enum(CardType))
    prompt: Mapped[dict[str, Any]] = mapped_column(JSONB)  # question/options/expected_points/anchor
    # SM-2 state
    ease_factor: Mapped[float] = mapped_column(Float, default=2.5)
    interval_days: Mapped[float] = mapped_column(Float, default=0.0)
    repetitions: Mapped[int] = mapped_column(Integer, default=0)
    lapses: Mapped[int] = mapped_column(Integer, default=0)
    consecutive_correct: Mapped[int] = mapped_column(Integer, default=0)
    due_at: Mapped[datetime] = mapped_column(index=True)
    status: Mapped[ItemStatus] = mapped_column(str_enum(ItemStatus), default=ItemStatus.ACTIVE)
    generation_version: Mapped[str] = mapped_column(String(10), default="v1")


class ReviewSession(ForgeTableMixin, Base):
    __tablename__ = "review_sessions"

    started_at: Mapped[datetime] = mapped_column()
    finished_at: Mapped[datetime | None] = mapped_column(nullable=True)
    items_total: Mapped[int] = mapped_column(Integer, default=0)
    items_correct: Mapped[int] = mapped_column(Integer, default=0)


class ReviewAttempt(ForgeTableMixin, Base):
    __tablename__ = "review_attempts"

    review_item_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("review_items.id", ondelete="CASCADE"), index=True
    )
    session_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("review_sessions.id", ondelete="SET NULL"), nullable=True
    )
    answered_at: Mapped[datetime] = mapped_column()
    user_answer: Mapped[str | None] = mapped_column(Text, nullable=True)
    grade: Mapped[int] = mapped_column(Integer)
    feedback: Mapped[str | None] = mapped_column(Text, nullable=True)  # LLM grading feedback
    latency_ms: Mapped[int] = mapped_column(Integer, default=0)
