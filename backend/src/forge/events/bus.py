"""In-process domain event bus.

Events are the seams between bounded contexts. Publishers emit typed events;
subscribers register per event type. Handlers that need to run asynchronously
subscribe via a Celery task name instead of a callable — the bus enqueues them.

The event names are the stable contract; this bus can later become an
outbox + real broker without touching publishers or subscribers.
"""

from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from typing import Any

import structlog

logger = structlog.get_logger(__name__)


@dataclass(frozen=True, kw_only=True)
class DomainEvent:
    """Base class; subclasses define `name` and their payload fields."""

    name: str = field(init=False, default="")

    def payload(self) -> dict[str, Any]:
        data = asdict(self)
        data.pop("name", None)
        return data


SyncHandler = Callable[[DomainEvent], None]

_sync_handlers: dict[str, list[SyncHandler]] = {}
_task_handlers: dict[str, list[str]] = {}


def subscribe(event_name: str, handler: SyncHandler) -> None:
    _sync_handlers.setdefault(event_name, []).append(handler)


def subscribe_task(event_name: str, task_name: str) -> None:
    """Route an event to a Celery task (payload passed as kwargs)."""
    _task_handlers.setdefault(event_name, []).append(task_name)


def clear_subscribers() -> None:
    """Test hook."""
    _sync_handlers.clear()
    _task_handlers.clear()


def publish(event: DomainEvent) -> None:
    log = logger.bind(event=event.name)
    for handler in _sync_handlers.get(event.name, []):
        handler(event)
    task_names = _task_handlers.get(event.name, [])
    if task_names:
        # Imported lazily so the API process doesn't require a worker runtime
        # just to import the bus.
        from forge.workers.celery_app import celery_app

        for task_name in task_names:
            celery_app.send_task(task_name, kwargs=event.payload())
            log.debug("event.dispatched", task=task_name)
