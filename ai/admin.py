"""Admin registration for AI jobs and call audit."""

from django.contrib import admin

from .models import AIJob, LLMCall


@admin.register(AIJob)
class AIJobAdmin(admin.ModelAdmin):
    list_display = ("task", "status", "valuation", "created_at", "finished_at")
    list_filter = ("status", "task")
    readonly_fields = ("result", "error", "payload")


@admin.register(LLMCall)
class LLMCallAdmin(admin.ModelAdmin):
    list_display = (
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
    list_filter = ("provider", "task", "success")
