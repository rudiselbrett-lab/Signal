from fastapi import APIRouter
from pydantic import BaseModel
from sqlalchemy import text

from forge import __version__
from forge.api.deps import DbSession

router = APIRouter(tags=["health"])


class HealthResponse(BaseModel):
    status: str
    version: str
    database: str


@router.get("/health", response_model=HealthResponse)
async def health(db: DbSession) -> HealthResponse:
    try:
        await db.execute(text("SELECT 1"))
        database = "ok"
    except Exception:
        database = "unreachable"
    return HealthResponse(status="ok", version=__version__, database=database)
