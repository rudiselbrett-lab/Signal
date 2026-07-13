import os

import pytest
from httpx import ASGITransport, AsyncClient

os.environ.setdefault("FORGE_ENV", "test")


@pytest.fixture
async def client():
    from forge.main import create_app

    app = create_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c
