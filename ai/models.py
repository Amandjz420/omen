"""AI orchestration models: the job queue and the per-call audit row."""

from __future__ import annotations

from django.db import models

from core.models import BaseModel


class JobStatus(models.TextChoices):
    QUEUED = "queued", "Queued"
    RUNNING = "running", "Running"
    DONE = "done", "Done"
    ERROR = "error", "Error"


class AIJob(BaseModel):
    """A queued AI task against a valuation.

    Endpoints enqueue a job and return its id immediately; the worker
    (``run_ai_worker``) picks it up and the frontend polls ``GET /api/jobs/{id}``.
    Designed to be swappable for Celery later without changing the API.
    """

    valuation = models.ForeignKey(
        "valuations.Valuation", on_delete=models.CASCADE, related_name="ai_jobs"
    )
    task = models.CharField(max_length=50)
    status = models.CharField(
        max_length=10, choices=JobStatus.choices, default=JobStatus.QUEUED, db_index=True
    )
    payload = models.JSONField(default=dict, blank=True)
    result = models.JSONField(null=True, blank=True)
    error = models.TextField(blank=True)
    started_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)

    class Meta(BaseModel.Meta):
        indexes = [models.Index(fields=["status", "created_at"])]

    def __str__(self) -> str:
        return f"AIJob({self.task}, {self.status})"


class LLMCall(BaseModel):
    """Audit row for a single provider call (one per LLM request).

    Lets us see spend per task and per case. ``est_cost`` is computed from a
    small in-code cost table keyed by model (see ``ai.costs``).
    """

    valuation = models.ForeignKey(
        "valuations.Valuation",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="llm_calls",
    )
    task = models.CharField(max_length=50)
    provider = models.CharField(max_length=30)
    model = models.CharField(max_length=120)
    prompt_tokens = models.IntegerField(default=0)
    completion_tokens = models.IntegerField(default=0)
    latency_ms = models.IntegerField(default=0)
    est_cost = models.DecimalField(max_digits=12, decimal_places=6, default=0)
    success = models.BooleanField(default=True)
    error = models.TextField(blank=True)

    def __str__(self) -> str:
        return f"LLMCall({self.task}/{self.model}, ${self.est_cost})"
