"""FastAPI dependency wiring."""

from collections.abc import AsyncIterator
from typing import Annotated
from uuid import UUID

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from forge.adapters.persistence.db import get_session_factory
from forge.config import DEFAULT_USER_ID, Settings, get_settings


async def get_db(  # commit-on-success unit of work per request
) -> AsyncIterator[AsyncSession]:
    async with get_session_factory()() as session:
        try:
            yield session
            await session.commit()
        except BaseException:
            await session.rollback()
            raise


async def get_current_user_id() -> UUID:
    """Single-user MVP: fixed identity. Swap for real auth without touching routers."""
    return DEFAULT_USER_ID


DbSession = Annotated[AsyncSession, Depends(get_db)]
CurrentUserId = Annotated[UUID, Depends(get_current_user_id)]
AppSettings = Annotated[Settings, Depends(get_settings)]
