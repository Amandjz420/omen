"""Valuation, media and answer routes (mounted under /api/)."""

from django.urls import path
from rest_framework.routers import DefaultRouter

from .views import (
    AnswerViewSet,
    MediaConfirmView,
    MediaPresignView,
    ValuationViewSet,
)

router = DefaultRouter(trailing_slash=False)
router.register("valuations", ValuationViewSet, basename="valuation")
router.register("answers", AnswerViewSet, basename="answer")

urlpatterns = [
    path("media/presign", MediaPresignView.as_view(), name="media-presign"),
    path("media/confirm", MediaConfirmView.as_view(), name="media-confirm"),
    *router.urls,
]
