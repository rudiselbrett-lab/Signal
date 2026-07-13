from datetime import datetime
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel, ConfigDict, Field

from forge.adapters.llm import AnthropicLLM
from forge.adapters.persistence.models.reinforcement import ReviewItem
from forge.adapters.persistence.repositories.reinforcement import SqlReinforcementRepository
from forge.api.deps import CurrentUserId, DbSession
from forge.services.reinforcement.service import ReinforcementService

router = APIRouter(prefix="/reviews", tags=["reviews"])


class ReviewItemOut(BaseModel):
    id: UUID
    article_id: UUID
    card_type: str
    question: str
    options: list[str] | None
    due_at: datetime
    interval_days: float
    repetitions: int

    @classmethod
    def from_item(cls, item: ReviewItem) -> "ReviewItemOut":
        # correct_option / expected_points are deliberately withheld.
        return cls(
            id=item.id,
            article_id=item.article_id,
            card_type=str(item.card_type),
            question=item.prompt.get("question", ""),
            options=item.prompt.get("options"),
            due_at=item.due_at,
            interval_days=item.interval_days,
            repetitions=item.repetitions,
        )


class SessionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    started_at: datetime
    finished_at: datetime | None
    items_total: int
    items_correct: int


class AnswerIn(BaseModel):
    item_id: UUID
    answer: str | None = Field(default=None, max_length=5000)
    choice_index: int | None = Field(default=None, ge=0, le=3)
    latency_ms: int = Field(default=0, ge=0)


class AttemptOut(BaseModel):
    grade: int
    feedback: str | None
    next_due_at: datetime
    interval_days: float
    prompt: dict[str, Any]  # revealed after answering (correct option, expected points)


def get_service(db: DbSession) -> ReinforcementService:
    return ReinforcementService(SqlReinforcementRepository(db), AnthropicLLM())


Service = Annotated[ReinforcementService, Depends(get_service)]


@router.get("/due", response_model=list[ReviewItemOut])
async def due_items(svc: Service, user_id: CurrentUserId) -> list[ReviewItemOut]:
    return [ReviewItemOut.from_item(i) for i in await svc.due_items(user_id)]


@router.get("/due/count")
async def due_count(svc: Service, user_id: CurrentUserId) -> dict[str, int]:
    return {"due": await svc.due_count(user_id)}


@router.post("/sessions", response_model=SessionOut, status_code=status.HTTP_201_CREATED)
async def start_session(svc: Service, user_id: CurrentUserId) -> SessionOut:
    return SessionOut.model_validate(await svc.start_session(user_id))


@router.post("/sessions/{session_id}/answers", response_model=AttemptOut)
async def submit_answer(
    session_id: UUID, data: AnswerIn, svc: Service, user_id: CurrentUserId
) -> AttemptOut:
    attempt, item = await svc.submit_answer(
        user_id,
        session_id,
        data.item_id,
        answer=data.answer,
        choice_index=data.choice_index,
        latency_ms=data.latency_ms,
    )
    return AttemptOut(
        grade=attempt.grade,
        feedback=attempt.feedback,
        next_due_at=item.due_at,
        interval_days=item.interval_days,
        prompt=item.prompt,
    )


@router.post("/sessions/{session_id}/finish", response_model=SessionOut)
async def finish_session(session_id: UUID, svc: Service, user_id: CurrentUserId) -> SessionOut:
    return SessionOut.model_validate(await svc.finish_session(user_id, session_id))
