"""Celery application.

Queues are isolated per workload so one misbehaving pipeline never starves
another (see ARCHITECTURE.md §10). All tasks must be idempotent.
"""

from celery import Celery
from celery.schedules import crontab

from forge.config import get_settings

settings = get_settings()

celery_app = Celery(
    "forge",
    broker=settings.redis_url,
    backend=settings.redis_url,
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    task_default_queue="default",
    task_routes={
        "forge.ingestion.*": {"queue": "ingestion"},
        "forge.enrichment.*": {"queue": "enrichment"},
        "forge.reviews.*": {"queue": "reviews"},
        "forge.analytics.*": {"queue": "analytics"},
    },
    beat_schedule={
        "discover-sources": {
            "task": "forge.ingestion.discover_all",
            "schedule": crontab(minute=0, hour=f"*/{settings.discovery_interval_hours}"),
            "options": {"queue": "ingestion"},
        },
    },
    timezone="UTC",
)

celery_app.autodiscover_tasks(["forge.workers"])

# Cross-context event reactions must be registered in every process that
# publishes or consumes domain events.
from forge.events.wiring import register_subscribers  # noqa: E402

register_subscribers()
