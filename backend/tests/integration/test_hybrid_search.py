"""Hybrid search integration tests against real Postgres + pgvector.

Embeddings are synthetic unit vectors so semantic ranking is fully
deterministic without calling a provider.
"""

import uuid

import pytest

from forge.adapters.persistence.models.content import Article
from forge.adapters.persistence.models.search import EMBEDDING_DIM, ArticleChunk
from forge.adapters.persistence.repositories.search import SqlSearchRepository
from forge.config import DEFAULT_USER_ID
from forge.domain.content import ArticleStatus

pytestmark = pytest.mark.integration

USER = DEFAULT_USER_ID


def unit_vector(axis: int) -> list[float]:
    v = [0.0] * EMBEDDING_DIM
    v[axis] = 1.0
    return v


def blend(a: int, b: int, weight: float) -> list[float]:
    v = [0.0] * EMBEDDING_DIM
    v[a] = weight
    v[b] = (1 - weight**2) ** 0.5
    return v


def make_article(title: str, status=ArticleStatus.LEARNED, embedding=None) -> Article:
    slug = title.lower().replace(" ", "-")
    return Article(
        id=uuid.uuid4(),
        user_id=USER,
        url=f"https://example.com/{slug}",
        canonical_url=f"https://example.com/{slug}",
        title=title,
        status=status,
        embedding=embedding,
    )


def make_chunk(article: Article, index: int, text: str, embedding: list[float]) -> ArticleChunk:
    return ArticleChunk(
        user_id=USER,
        article_id=article.id,
        chunk_index=index,
        text=text,
        token_count=len(text) // 4,
        embedding=embedding,
    )


@pytest.fixture
async def corpus(db_session):
    pg_article = make_article("Postgres indexing deep dive")
    k8s_article = make_article("Kubernetes autoscaling in practice")
    db_session.add_all([pg_article, k8s_article])
    await db_session.flush()
    db_session.add_all(
        [
            make_chunk(pg_article, 0, "BTree indexes accelerate range scans.", unit_vector(0)),
            make_chunk(
                pg_article, 1, "Partial indexes reduce write amplification.", blend(0, 5, 0.9)
            ),
            make_chunk(pg_article, 2, "HNSW indexes support vector search.", blend(0, 6, 0.8)),
            make_chunk(
                k8s_article, 0, "Horizontal pod autoscaling reacts to load.", unit_vector(1)
            ),
        ]
    )
    await db_session.commit()
    return pg_article, k8s_article


async def test_semantic_match_wins_without_keyword_overlap(db_session, corpus):
    pg_article, _ = corpus
    repo = SqlSearchRepository(db_session)
    # Query vector near axis 0; query text shares no words with any chunk.
    hits = await repo.hybrid_search(USER, "zzzz nonexistent words", unit_vector(0), limit=4)
    assert hits, "semantic leg alone should return results"
    assert hits[0].article_id == pg_article.id


async def test_keyword_match_found_even_when_semantically_far(db_session, corpus):
    _, k8s_article = corpus
    repo = SqlSearchRepository(db_session)
    # Query vector points at postgres axis, but the words match the k8s chunk.
    hits = await repo.hybrid_search(USER, "horizontal pod autoscaling", unit_vector(0), limit=4)
    assert any(h.article_id == k8s_article.id for h in hits)


async def test_rrf_fusion_ranks_double_leg_hits_first(db_session, corpus):
    pg_article, _ = corpus
    repo = SqlSearchRepository(db_session)
    # Both legs point at the BTree chunk: semantic axis 0 + keyword "range scans".
    hits = await repo.hybrid_search(USER, "range scans", unit_vector(0), limit=4)
    assert hits[0].article_id == pg_article.id
    assert "range scans" in hits[0].chunk_text.lower()


async def test_per_article_cap_limits_chunks(db_session, corpus):
    pg_article, _ = corpus
    repo = SqlSearchRepository(db_session)
    hits = await repo.hybrid_search(USER, "indexes", unit_vector(0), limit=10, per_article=2)
    pg_hits = [h for h in hits if h.article_id == pg_article.id]
    assert len(pg_hits) <= 2


async def test_max_similarity_to_library(db_session, corpus):
    repo = SqlSearchRepository(db_session)
    corpus[0].embedding = unit_vector(0)
    corpus[1].embedding = unit_vector(1)
    await db_session.commit()

    sim = await repo.max_similarity_to_library(USER, blend(0, 1, 0.95), ["learned"])
    assert sim is not None
    assert 0.94 <= sim <= 0.96

    none_sim = await repo.max_similarity_to_library(USER, unit_vector(0), ["mastered"])
    assert none_sim is None
