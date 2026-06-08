"""Serializers for the verification workflow."""

from __future__ import annotations

from rest_framework import serializers

from .models import StageReview


class StageReviewSerializer(serializers.ModelSerializer):
    class Meta:
        model = StageReview
        fields = (
            "id",
            "valuation",
            "stage",
            "status",
            "actor",
            "reason",
            "ai_flags",
            "acted_at",
        )
        read_only_fields = fields


class RevertSerializer(serializers.Serializer):
    reason = serializers.CharField()
