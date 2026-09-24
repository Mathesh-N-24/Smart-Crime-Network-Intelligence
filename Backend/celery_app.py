"""
celery_app.py
============================================================================
Celery application factory. Kept separate from tasks.py so both the
FastAPI process (which only needs to *enqueue* tasks) and the worker
process (which *executes* them) can import a lightweight app object
without pulling in the full AI-pipeline dependency tree unnecessarily.
============================================================================
"""

import os
from celery import Celery

CELERY_BROKER_URL = os.getenv("CELERY_BROKER_URL", "redis://localhost:6379/0")
CELERY_RESULT_BACKEND = os.getenv("CELERY_RESULT_BACKEND", "redis://localhost:6379/1")

celery_app = Celery(
    "cnas",
    broker=CELERY_BROKER_URL,
    backend=CELERY_RESULT_BACKEND,
    include=["tasks"],
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    result_expires=3600,
    task_track_started=True,
    # Air-gapped/offline-friendly: no need for long-lived broker connection
    # retries against an external service that will never appear.
    broker_connection_retry_on_startup=True,
)
