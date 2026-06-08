"""Verification routes (mounted under /api/)."""

from django.urls import path

from .views import (
    StageActionView,
    VerificationDetailView,
    VerificationQueueView,
)

urlpatterns = [
    path("verification/queue", VerificationQueueView.as_view(), name="verification-queue"),
    path(
        "verification/<uuid:valuation_id>",
        VerificationDetailView.as_view(),
        name="verification-detail",
    ),
    path(
        "verification/<uuid:valuation_id>/<str:stage>/<str:action>",
        StageActionView.as_view(),
        name="verification-action",
    ),
]
