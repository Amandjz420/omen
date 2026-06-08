"""Admin registration for verification reviews."""

from django.contrib import admin

from .models import StageReview


@admin.register(StageReview)
class StageReviewAdmin(admin.ModelAdmin):
    list_display = ("valuation", "stage", "status", "actor", "acted_at")
    list_filter = ("stage", "status")
