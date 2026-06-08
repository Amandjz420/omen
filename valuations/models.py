"""Core valuation case models: Valuation, MediaAsset, Answer, MarketRateLookup."""

from __future__ import annotations

from django.conf import settings
from django.db import models

from core.models import BaseModel
from leads.models import WorkOrder
from masters.models import Question


class ValuationStatus(models.TextChoices):
    DRAFT = "draft", "Draft"
    IN_PROGRESS = "in_progress", "In Progress"
    SUBMITTED = "submitted", "Submitted for verification"
    IN_VERIFICATION = "in_verification", "In Verification"
    APPROVED = "approved", "Approved"
    REVERTED = "reverted", "Reverted to valuer"


class Valuation(BaseModel):
    """A valuation case, 1:1 with a :class:`WorkOrder`."""

    work_order = models.OneToOneField(
        WorkOrder, on_delete=models.PROTECT, related_name="valuation"
    )
    status = models.CharField(
        max_length=20, choices=ValuationStatus.choices, default=ValuationStatus.DRAFT
    )
    assigned_valuer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="valuations",
    )
    latitude = models.DecimalField(
        max_digits=9, decimal_places=6, null=True, blank=True
    )
    longitude = models.DecimalField(
        max_digits=9, decimal_places=6, null=True, blank=True
    )
    address = models.TextField(blank=True)
    locality = models.CharField(max_length=200, blank=True)

    def __str__(self) -> str:
        return f"Valuation {self.id} ({self.work_order.reference})"


class MediaKind(models.TextChoices):
    AUDIO = "audio", "Audio"
    PHOTO = "photo", "Photo"
    DOCUMENT = "document", "Document"
    SKETCH = "sketch", "Sketch"


class MediaAsset(BaseModel):
    """A file uploaded for a valuation (audio/photo/document/sketch).

    The browser uploads directly to S3 via a presigned PUT; ``uploaded`` flips
    to True on the confirm step. AI tasks write their per-asset output back into
    ``transcript`` (ASR) and ``extraction`` (doc/photo analysis).
    """

    valuation = models.ForeignKey(
        Valuation, on_delete=models.CASCADE, related_name="media_assets"
    )
    kind = models.CharField(max_length=20, choices=MediaKind.choices)
    s3_key = models.CharField(max_length=500)
    mime = models.CharField(max_length=120, blank=True)
    filename = models.CharField(max_length=255, blank=True)
    size = models.BigIntegerField(null=True, blank=True)
    duration = models.FloatField(null=True, blank=True, help_text="Seconds, for audio")
    latitude = models.DecimalField(
        max_digits=9, decimal_places=6, null=True, blank=True
    )
    longitude = models.DecimalField(
        max_digits=9, decimal_places=6, null=True, blank=True
    )
    uploaded = models.BooleanField(default=False)

    # AI outputs
    transcript = models.JSONField(
        null=True, blank=True, help_text="{text, language, english}"
    )
    extraction = models.JSONField(
        null=True, blank=True, help_text="Structured fields from doc/photo analysis"
    )

    def __str__(self) -> str:
        return f"{self.kind} {self.filename or self.s3_key}"


class Confidence(models.TextChoices):
    GREEN = "green", "Green (high)"
    AMBER = "amber", "Amber (review)"
    RED = "red", "Red (missing/low)"


class Answer(BaseModel):
    """An answer to a Question for a given Valuation.

    ``evidence`` links the answer back to its sources: a list of
    ``{asset_id, snippet}`` so reviewers can trace every AI-filled value.
    """

    valuation = models.ForeignKey(
        Valuation, on_delete=models.CASCADE, related_name="answers"
    )
    question = models.ForeignKey(Question, on_delete=models.PROTECT)
    value = models.JSONField(null=True, blank=True)
    confidence = models.CharField(
        max_length=10, choices=Confidence.choices, default=Confidence.RED
    )
    confirmed = models.BooleanField(default=False)
    evidence = models.JSONField(default=list, blank=True)
    ai_filled = models.BooleanField(default=False)

    class Meta(BaseModel.Meta):
        unique_together = ("valuation", "question")

    def __str__(self) -> str:
        return f"Answer({self.question_id}) = {self.value!r}"


class MarketRateLookup(BaseModel):
    """A market-rate search result (from Perplexity) surfaced to the valuer."""

    valuation = models.ForeignKey(
        Valuation, on_delete=models.CASCADE, related_name="market_rates"
    )
    query = models.TextField()
    result_range = models.JSONField(
        null=True, blank=True, help_text="{min, max, unit, currency}"
    )
    citations = models.JSONField(default=list, blank=True)
    raw_response = models.JSONField(null=True, blank=True)

    def __str__(self) -> str:
        return f"MarketRate({self.valuation_id})"
