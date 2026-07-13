import pytest
from httpx import ASGITransport, AsyncClient

from forge.services.sources.service import SourcesService
from tests.fakes import FakeSourcesRepository


@pytest.fixture
async def client():
    from forge.api.v1.sources import get_sources_service
    from forge.main import create_app

    app = create_app()
    repo = FakeSourcesRepository()
    app.dependency_overrides[get_sources_service] = lambda: SourcesService(repo)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


async def test_source_crud_roundtrip(client):
    created = await client.post(
        "/api/v1/sources",
        json={
            "name": "Netflix Tech Blog",
            "source_type": "rss",
            "config": {"feed_url": "https://netflixtechblog.com/feed"},
        },
    )
    assert created.status_code == 201, created.text
    source = created.json()
    assert source["status"] == "active"

    listed = (await client.get("/api/v1/sources")).json()
    assert [s["id"] for s in listed] == [source["id"]]

    patched = await client.patch(f"/api/v1/sources/{source['id']}", json={"enabled": False})
    assert patched.json()["enabled"] is False

    deleted = await client.delete(f"/api/v1/sources/{source['id']}")
    assert deleted.status_code == 204
    assert (await client.get("/api/v1/sources")).json() == []


async def test_invalid_config_returns_problem_details(client):
    resp = await client.post(
        "/api/v1/sources",
        json={"name": "bad", "source_type": "rss", "config": {}},
    )
    assert resp.status_code == 422
    assert resp.headers["content-type"].startswith("application/problem+json")


async def test_presets_listed(client):
    resp = await client.get("/api/v1/sources/presets")
    assert resp.status_code == 200
    names = [p["name"] for p in resp.json()]
    assert "Anthropic News" in names
