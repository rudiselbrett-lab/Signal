"""Celery application.

Queues are isolated per workload so one misbehaving pipeline never starves
another (see ARCHITECTURE.md §10). All tasks must be idempotent.
"""

from celery import Celery

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
    beat_schedule={},  # populated by forge.workers.schedule
    timezone="UTC",
)

celery_app.autodiscover_tasks(["forge.workers"])
