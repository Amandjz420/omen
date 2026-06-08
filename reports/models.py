"""Report-side models.

Reports are generated on demand (PDF rendered to S3), so there is no persistent
report row yet. The stubs below — Invoice / Dispatch / PayInReceipt — are
placeholders that will connect to the existing/legacy billing system later. They
are intentionally minimal; do not build business logic on them now.
"""

from __future__ import annotations

from django.db import models

from core.models import BaseModel
from valuations.models import Valuation


class Invoice(BaseModel):
    """STUB — connects to the legacy billing system later."""

    valuation = models.ForeignKey(
        Valuation, on_delete=models.CASCADE, related_name="invoices"
    )
    number = models.CharField(max_length=60, blank=True)
    amount = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    note = models.TextField(blank=True, default="STUB: wire to legacy system")

    def __str__(self) -> str:
        return f"Invoice(stub) {self.number}"


class Dispatch(BaseModel):
    """STUB — report dispatch tracking, wired later."""

    valuation = models.ForeignKey(
        Valuation, on_delete=models.CASCADE, related_name="dispatches"
    )
    channel = models.CharField(max_length=40, blank=True)
    note = models.TextField(blank=True, default="STUB: wire to legacy system")

    def __str__(self) -> str:
        return f"Dispatch(stub) {self.valuation_id}"


class PayInReceipt(BaseModel):
    """STUB — payment receipt, wired later."""

    valuation = models.ForeignKey(
        Valuation, on_delete=models.CASCADE, related_name="receipts"
    )
    amount = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    note = models.TextField(blank=True, default="STUB: wire to legacy system")

    def __str__(self) -> str:
        return f"PayInReceipt(stub) {self.valuation_id}"
