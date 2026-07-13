"""Reinforcement tasks."""

import asyncio
from uuid import UUID

from forge.adapters.llm import AnthropicLLM
from forge.adapters.persistence.db import session_scope
from forge.adapters.persistence.repositories.reinforcement import SqlReinforcementRepository
from forge.config import DEFAULT_USER_ID
from forge.services.reinforcement.service import CardNotReadyError, ReinforcementService
from forge.workers.celery_app import celery_app


@celery_app.task(
    name="forge.reviews.generate_items",
    autoretry_for=(CardNotReadyError, Exception),
    retry_backoff=30,  # extraction may still be running; back off generously
    retry_kwargs={"max_retries": 5},
)
def generate_items(article_id: str, user_id: str) -> None:
    asyncio.run(_generate_items(UUID(article_id), UUID(user_id)))


async def _generate_items(article_id: UUID, user_id: UUID) -> None:
    async with session_scope() as session:
        service = ReinforcementService(SqlReinforcementRepository(session), AnthropicLLM())
        await service.generate_items(user_id, article_id)


@celery_app.task(name="forge.reviews.materialize_due")
def materialize_due() -> int:
    return asyncio.run(_materialize_due())


async def _materialize_due() -> int:
    async with session_scope() as session:
        service = ReinforcementService(SqlReinforcementRepository(session), AnthropicLLM())
        return await service.materialize_due_statuses(DEFAULT_USER_ID)
