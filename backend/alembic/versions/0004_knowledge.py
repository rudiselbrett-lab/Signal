"""knowledge cards and entities

Revision ID: 0004
Revises: 0003
Create Date: 2026-07-13

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID

revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _timestamps() -> list[sa.Column]:
    return [
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    ]


def upgrade() -> None:
    op.create_table(
        "knowledge_cards",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", UUID(as_uuid=True), nullable=False),
        sa.Column(
            "article_id",
            UUID(as_uuid=True),
            sa.ForeignKey("articles.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
        ),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("key_ideas", JSONB(), nullable=False),
        sa.Column("mental_models", JSONB(), nullable=False),
        sa.Column("frameworks", JSONB(), nullable=False),
        sa.Column("topics", ARRAY(sa.Text()), nullable=False),
        sa.Column("tags", ARRAY(sa.Text()), nullable=False),
        sa.Column("difficulty", sa.String(32), nullable=False),
        sa.Column("extraction_version", sa.String(10), nullable=False),
        *_timestamps(),
    )
    op.create_index("ix_knowledge_cards_user_id", "knowledge_cards", ["user_id"])
    op.create_index(
        "ix_knowledge_cards_topics", "knowledge_cards", ["topics"], postgresql_using="gin"
    )

    op.create_table(
        "entities",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("kind", sa.String(32), nullable=False),
        sa.Column("normalized_name", sa.String(200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        *_timestamps(),
        sa.UniqueConstraint("user_id", "kind", "normalized_name", name="uq_entities_user_id"),
    )
    op.create_index("ix_entities_user_id", "entities", ["user_id"])

    op.create_table(
        "article_entities",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", UUID(as_uuid=True), nullable=False),
        sa.Column(
            "article_id",
            UUID(as_uuid=True),
            sa.ForeignKey("articles.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "entity_id",
            UUID(as_uuid=True),
            sa.ForeignKey("entities.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("salience", sa.Float(), nullable=False),
        *_timestamps(),
        sa.UniqueConstraint("article_id", "entity_id", name="uq_article_entities_article_id"),
    )
    op.create_index("ix_article_entities_user_id", "article_entities", ["user_id"])
    op.create_index("ix_article_entities_article_id", "article_entities", ["article_id"])
    op.create_index("ix_article_entities_entity_id", "article_entities", ["entity_id"])


def downgrade() -> None:
    op.drop_table("article_entities")
    op.drop_table("entities")
    op.drop_table("knowledge_cards")
