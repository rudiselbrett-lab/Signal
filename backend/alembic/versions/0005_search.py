"""article chunks, embeddings, hybrid search function

Revision ID: 0005
Revises: 0004
Create Date: 2026-07-13

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects.postgresql import TSVECTOR, UUID

revision: str = "0005"
down_revision: str | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

DIM = 1536

HYBRID_SEARCH_FN = f"""
CREATE OR REPLACE FUNCTION hybrid_search(
    p_user_id uuid,
    p_query text,
    p_embedding vector({DIM}),
    p_limit int DEFAULT 12,
    p_per_article int DEFAULT 3,
    p_candidates int DEFAULT 50,
    p_rrf_k int DEFAULT 60
) RETURNS TABLE (
    chunk_id uuid,
    article_id uuid,
    chunk_index int,
    chunk_text text,
    semantic_rank int,
    keyword_rank int,
    score double precision
) LANGUAGE sql STABLE AS $$
WITH semantic AS (
    SELECT c.id, row_number() OVER (ORDER BY c.embedding <=> p_embedding) AS rank
    FROM article_chunks c
    WHERE c.user_id = p_user_id AND c.embedding IS NOT NULL
    ORDER BY c.embedding <=> p_embedding
    LIMIT p_candidates
),
keyword AS (
    SELECT id, row_number() OVER (ORDER BY kw_score DESC) AS rank
    FROM (
        SELECT c.id, ts_rank_cd(c.tsv, websearch_to_tsquery('english', p_query)) AS kw_score
        FROM article_chunks c
        WHERE c.user_id = p_user_id
          AND c.tsv @@ websearch_to_tsquery('english', p_query)
        ORDER BY kw_score DESC
        LIMIT p_candidates
    ) ranked_kw
),
fused AS (
    SELECT COALESCE(s.id, k.id) AS id,
           s.rank AS semantic_rank,
           k.rank AS keyword_rank,
           COALESCE(1.0 / (p_rrf_k + s.rank), 0) + COALESCE(1.0 / (p_rrf_k + k.rank), 0) AS score
    FROM semantic s
    FULL OUTER JOIN keyword k USING (id)
),
capped AS (
    SELECT c.id AS chunk_id, c.article_id, c.chunk_index, c.text AS chunk_text,
           f.semantic_rank::int, f.keyword_rank::int, f.score,
           row_number() OVER (PARTITION BY c.article_id ORDER BY f.score DESC) AS article_rank
    FROM fused f
    JOIN article_chunks c ON c.id = f.id
)
SELECT chunk_id, article_id, chunk_index, chunk_text, semantic_rank, keyword_rank, score
FROM capped
WHERE article_rank <= p_per_article
ORDER BY score DESC
LIMIT p_limit;
$$;
"""


def upgrade() -> None:
    op.create_table(
        "article_chunks",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", UUID(as_uuid=True), nullable=False),
        sa.Column(
            "article_id",
            UUID(as_uuid=True),
            sa.ForeignKey("articles.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("token_count", sa.Integer(), nullable=False),
        sa.Column("embedding", Vector(DIM), nullable=True),
        sa.Column(
            "tsv",
            TSVECTOR(),
            sa.Computed("to_tsvector('english', text)", persisted=True),
            nullable=True,
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.UniqueConstraint("article_id", "chunk_index", name="uq_article_chunks_article_id"),
    )
    op.create_index("ix_article_chunks_user_id", "article_chunks", ["user_id"])
    op.create_index("ix_article_chunks_article_id", "article_chunks", ["article_id"])
    op.create_index(
        "ix_article_chunks_embedding",
        "article_chunks",
        ["embedding"],
        postgresql_using="hnsw",
        postgresql_ops={"embedding": "vector_cosine_ops"},
    )
    op.create_index("ix_article_chunks_tsv", "article_chunks", ["tsv"], postgresql_using="gin")

    op.add_column("articles", sa.Column("embedding", Vector(DIM), nullable=True))
    op.add_column("articles", sa.Column("embedding_version", sa.String(20), nullable=True))
    op.create_index(
        "ix_articles_embedding",
        "articles",
        ["embedding"],
        postgresql_using="hnsw",
        postgresql_ops={"embedding": "vector_cosine_ops"},
    )

    op.execute(HYBRID_SEARCH_FN)


def downgrade() -> None:
    op.execute("DROP FUNCTION IF EXISTS hybrid_search")
    op.drop_index("ix_articles_embedding", "articles")
    op.drop_column("articles", "embedding_version")
    op.drop_column("articles", "embedding")
    op.drop_table("article_chunks")
