"""Enqueue + execute :class:`AIJob` rows.

This is a deliberately simple DB-backed queue (no Celery/Redis yet). The
``enqueue``/``run_job`` seam matches what a Celery task would look like, so we
can swap the backend later without touching the API or task functions.
"""

from __future__ import annotations

import logging
import traceback

from django.utils import timezone

from .models import AIJob, JobStatus
from .services import TASK_FUNCTIONS

logger = logging.getLogger("omen.ai")


def enqueue(valuation, task: str, payload: dict | None = None) -> AIJob:
    """Create a queued job for ``task`` against ``valuation``."""
    if task not in TASK_FUNCTIONS:
        raise ValueError(f"Unknown AI task: {task!r}")
    return AIJob.objects.create(valuation=valuation, task=task, payload=payload or {})


def run_job(job: AIJob) -> AIJob:
    """Execute a single job, recording status, result and errors.

    Safe to call from the worker; never raises for task failures (they are
    captured onto the job as ``error``).
    """
    job.status = JobStatus.RUNNING
    job.started_at = timezone.now()
    job.save(update_fields=["status", "started_at", "updated_at"])

    func = TASK_FUNCTIONS[job.task]
    try:
        result = func(job.valuation)
        job.result = result
        job.status = JobStatus.DONE
        job.error = ""
    except Exception as exc:  # noqa: BLE001 - capture any task failure
        logger.exception("AIJob %s (%s) failed", job.id, job.task)
        job.status = JobStatus.ERROR
        job.error = f"{exc}\n{traceback.format_exc()}"[:5000]
    finally:
        job.finished_at = timezone.now()
        job.save(update_fields=["status", "result", "error", "finished_at", "updated_at"])
    return job


def process_queued(batch: int = 5) -> int:
    """Run up to ``batch`` queued jobs (oldest first). Returns count processed."""
    jobs = AIJob.objects.filter(status=JobStatus.QUEUED).order_by("created_at")[:batch]
    count = 0
    for job in jobs:
        run_job(job)
        count += 1
    return count
