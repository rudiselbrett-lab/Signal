"""article scores and llm call log

Revision ID: 0003
Revises: 0002
Create Date: 2026-07-13

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "article_scores",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", UUID(as_uuid=True), nullable=False),
        sa.Column(
            "article_id",
            UUID(as_uuid=True),
            sa.ForeignKey("articles.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
        ),
        sa.Column("overall", sa.Integer(), nullable=False),
        sa.Column("relevance", sa.Integer(), nullable=False),
        sa.Column("novelty", sa.Integer(), nullable=False),
        sa.Column("credibility", sa.Integer(), nullable=False),
        sa.Column("practicality", sa.Integer(), nullable=False),
        sa.Column("knowledge_gap", sa.Integer(), nullable=False),
        sa.Column("reading_time_bonus", sa.Integer(), nullable=False),
        sa.Column("difficulty", sa.String(32), nullable=False),
        sa.Column("rationale", JSONB(), nullable=False),
        sa.Column("scoring_version", sa.String(10), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    op.create_index("ix_article_scores_user_id", "article_scores", ["user_id"])
    op.create_index("ix_article_scores_overall", "article_scores", ["overall"])

    op.create_table(
        "llm_calls",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", UUID(as_uuid=True), nullable=False),
        sa.Column("prompt_name", sa.String(100), nullable=False),
        sa.Column("model", sa.String(100), nullable=False),
        sa.Column("input_tokens", sa.Integer(), nullable=False),
        sa.Column("output_tokens", sa.Integer(), nullable=False),
        sa.Column("latency_ms", sa.Integer(), nullable=False),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    op.create_index("ix_llm_calls_user_id", "llm_calls", ["user_id"])
    op.create_index("ix_llm_calls_prompt_name", "llm_calls", ["prompt_name"])


def downgrade() -> None:
    op.drop_table("llm_calls")
    op.drop_table("article_scores")
