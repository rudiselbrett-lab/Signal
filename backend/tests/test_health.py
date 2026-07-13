async def test_health_returns_ok_without_database(client):
    resp = await client.get("/api/v1/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    # No Postgres in unit-test runs: the endpoint degrades, never 500s.
    assert body["database"] in ("ok", "unreachable")


async def test_openapi_schema_is_served(client):
    resp = await client.get("/api/openapi.json")
    assert resp.status_code == 200
    assert resp.json()["info"]["title"] == "Forge API"
