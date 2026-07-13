"""Integration fixtures: real Postgres with pgvector.

Runs only when FORGE_TEST_DATABASE_URL is set (locally or in CI); migrations
are applied once per session, and each test runs in a truncated schema.
"""

import os
import subprocess
from pathlib import Path

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

TEST_DB_URL = os.environ.get("FORGE_TEST_DATABASE_URL")

pytestmark = pytest.mark.integration

TABLES = [
    "article_chunks",
    "article_entities",
    "knowledge_cards",
    "entities",
    "article_scores",
    "llm_calls",
    "articles",
    "discovery_runs",
    "sources",
    "categories",
]


@pytest.fixture(scope="session")
def migrated_db_url() -> str:
    if not TEST_DB_URL:
        pytest.skip("FORGE_TEST_DATABASE_URL not set")
    backend_dir = Path(__file__).resolve().parents[2]
    subprocess.run(
        ["uv", "run", "alembic", "upgrade", "head"],
        cwd=backend_dir,
        env={**os.environ, "FORGE_DATABASE_URL": TEST_DB_URL},
        check=True,
        capture_output=True,
    )
    return TEST_DB_URL


@pytest.fixture
async def db_session(migrated_db_url):
    engine = create_async_engine(migrated_db_url)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        await session.execute(text(f"TRUNCATE {', '.join(TABLES)} CASCADE"))
        await session.commit()
        yield session
        await session.rollback()
    await engine.dispose()
