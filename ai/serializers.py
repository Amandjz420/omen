"""Serializers for AI jobs and audit rows."""

from __future__ import annotations

from rest_framework import serializers

from .models import AIJob, LLMCall


class AIJobSerializer(serializers.ModelSerializer):
    class Meta:
        model = AIJob
        fields = (
            "id",
            "valuation",
            "task",
            "status",
            "result",
            "error",
            "created_at",
            "started_at",
            "finished_at",
        )
        read_only_fields = fields


class LLMCallSerializer(serializers.ModelSerializer):
    class Meta:
        model = LLMCall
        fields = (
            "id",
            "valuation",
            "task",
            "provider",
            "model",
            "prompt_tokens",
            "completion_tokens",
            "latency_ms",
            "est_cost",
            "success",
            "created_at",
        )
        read_only_fields = fields
