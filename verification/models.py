"""6-stage human verification workflow with AI risk flags.

Stages run in order; each can be approved (advance) or reverted (send back to the
valuer with a reason). AI risk flags are attached per stage review for the human
to consider — humans always sign off.
"""

from __future__ import annotations

from django.conf import settings
from django.db import models

from core.models import BaseModel
from valuations.models import Valuation


class Stage(models.TextChoices):
    LEGAL = "legal", "Legal"
    SOCIAL = "social", "Social"
    TECHNICAL = "technical", "Technical"
    GENERAL = "general", "General"
    FINAL_APPROVAL = "final_approval", "Final approval"
    REVERT = "revert", "Revert"


# The ordered pipeline (revert is an action/target, not a forward step).
STAGE_ORDER = [
    Stage.LEGAL,
    Stage.SOCIAL,
    Stage.TECHNICAL,
    Stage.GENERAL,
    Stage.FINAL_APPROVAL,
]


class ReviewStatus(models.TextChoices):
    PENDING = "pending", "Pending"
    APPROVED = "approved", "Approved"
    REVERTED = "reverted", "Reverted"


class StageReview(BaseModel):
    """The state + outcome of one verification stage for a valuation."""

    valuation = models.ForeignKey(
        Valuation, on_delete=models.CASCADE, related_name="stage_reviews"
    )
    stage = models.CharField(max_length=20, choices=Stage.choices)
    status = models.CharField(
        max_length=10, choices=ReviewStatus.choices, default=ReviewStatus.PENDING
    )
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True
    )
    reason = models.TextField(blank=True)
    ai_flags = models.JSONField(default=list, blank=True)
    acted_at = models.DateTimeField(null=True, blank=True)

    class Meta(BaseModel.Meta):
        unique_together = ("valuation", "stage")

    def __str__(self) -> str:
        return f"{self.valuation_id} / {self.stage}: {self.status}"
