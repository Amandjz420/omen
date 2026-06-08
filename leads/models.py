"""Leads and work orders.

A :class:`WorkOrder` is the contract that defines *which questions apply* to a
valuation: client + orderer + service type + sub-type + bank.
"""

from __future__ import annotations

from django.conf import settings
from django.db import models

from core.models import BaseModel
from masters.models import Bank, Orderer, ServiceSubType, ServiceType


class LeadStatus(models.TextChoices):
    NEW = "new", "New"
    QUALIFIED = "qualified", "Qualified"
    CONVERTED = "converted", "Converted"
    LOST = "lost", "Lost"


class Lead(BaseModel):
    """An inbound enquiry that may become a work order."""

    title = models.CharField(max_length=200)
    bank = models.ForeignKey(
        Bank, on_delete=models.SET_NULL, null=True, blank=True, related_name="leads"
    )
    contact_name = models.CharField(max_length=200, blank=True)
    contact_phone = models.CharField(max_length=20, blank=True)
    notes = models.TextField(blank=True)
    status = models.CharField(
        max_length=20, choices=LeadStatus.choices, default=LeadStatus.NEW
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True
    )

    def __str__(self) -> str:
        return self.title


class WorkOrderStatus(models.TextChoices):
    OPEN = "open", "Open"
    ASSIGNED = "assigned", "Assigned"
    COMPLETED = "completed", "Completed"
    CANCELLED = "cancelled", "Cancelled"


class WorkOrder(BaseModel):
    """A work order carrying everything needed to scope a valuation."""

    reference = models.CharField(max_length=60, unique=True)
    lead = models.ForeignKey(
        Lead, on_delete=models.SET_NULL, null=True, blank=True, related_name="work_orders"
    )
    bank = models.ForeignKey(Bank, on_delete=models.PROTECT, related_name="work_orders")
    orderer = models.ForeignKey(
        Orderer, on_delete=models.SET_NULL, null=True, blank=True
    )
    service_type = models.ForeignKey(ServiceType, on_delete=models.PROTECT)
    sub_type = models.ForeignKey(
        ServiceSubType, on_delete=models.PROTECT, null=True, blank=True
    )
    property_address = models.TextField(blank=True)
    status = models.CharField(
        max_length=20, choices=WorkOrderStatus.choices, default=WorkOrderStatus.OPEN
    )

    def __str__(self) -> str:
        return f"WO {self.reference} ({self.bank.name})"
