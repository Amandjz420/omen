"""Serializers for leads and work orders."""

from __future__ import annotations

from rest_framework import serializers

from .models import Lead, WorkOrder


class LeadSerializer(serializers.ModelSerializer):
    class Meta:
        model = Lead
        fields = (
            "id",
            "title",
            "bank",
            "contact_name",
            "contact_phone",
            "notes",
            "status",
            "created_by",
            "created_at",
        )
        read_only_fields = ("created_by", "created_at")


class WorkOrderSerializer(serializers.ModelSerializer):
    bank_name = serializers.CharField(source="bank.name", read_only=True)
    service_type_name = serializers.CharField(source="service_type.name", read_only=True)
    sub_type_name = serializers.CharField(source="sub_type.name", read_only=True, default=None)

    class Meta:
        model = WorkOrder
        fields = (
            "id",
            "reference",
            "lead",
            "bank",
            "bank_name",
            "orderer",
            "service_type",
            "service_type_name",
            "sub_type",
            "sub_type_name",
            "property_address",
            "status",
            "created_at",
        )
        read_only_fields = ("created_at",)
