"""Verification queue + per-stage approve/revert endpoints."""

from __future__ import annotations

from django.shortcuts import get_object_or_404
from django.utils import timezone
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from core.permissions import IsValuerOrVerifier
from valuations.models import Valuation, ValuationStatus
from valuations.serializers import AnswerSerializer

from .models import ReviewStatus, Stage, StageReview
from .serializers import RevertSerializer, StageReviewSerializer


class VerificationQueueView(APIView):
    """``GET /api/verification/queue?stage=`` → cases awaiting a stage."""

    permission_classes = [IsAuthenticated, IsValuerOrVerifier]

    @extend_schema(parameters=[OpenApiParameter("stage", str, required=False)])
    def get(self, request):
        stage = request.query_params.get("stage", Stage.LEGAL)
        # Cases that are submitted/in-verification and not yet approved at `stage`.
        valuations = Valuation.objects.filter(
            status__in=[ValuationStatus.SUBMITTED, ValuationStatus.IN_VERIFICATION]
        ).exclude(
            stage_reviews__stage=stage, stage_reviews__status=ReviewStatus.APPROVED
        )
        data = [
            {
                "valuation_id": str(v.id),
                "work_order": v.work_order.reference,
                "status": v.status,
                "locality": v.locality,
            }
            for v in valuations.select_related("work_order")
        ]
        return Response({"stage": stage, "results": data})


class VerificationDetailView(APIView):
    """``GET /api/verification/{valuation_id}`` → answers + AI risk flags."""

    permission_classes = [IsAuthenticated, IsValuerOrVerifier]

    def get(self, request, valuation_id):
        valuation = get_object_or_404(Valuation, id=valuation_id)
        answers = valuation.answers.select_related("question").all()
        reviews = valuation.stage_reviews.all()
        # Fresh, stage-agnostic risk flags for the reviewer.
        from ai.services import run_risk_checks

        risk = run_risk_checks(valuation, stage=None)
        return Response(
            {
                "valuation_id": str(valuation.id),
                "status": valuation.status,
                "answers": AnswerSerializer(answers, many=True).data,
                "stage_reviews": StageReviewSerializer(reviews, many=True).data,
                "ai_risk_flags": risk["flags"],
            }
        )


class StageActionView(APIView):
    """Approve or revert a single verification stage.

    * ``POST /api/verification/{valuation_id}/{stage}/approve``
    * ``POST /api/verification/{valuation_id}/{stage}/revert`` (body: ``{reason}``)
    """

    permission_classes = [IsAuthenticated, IsValuerOrVerifier]

    def _get_review(self, valuation, stage):
        # Compute AI risk flags for this stage at review time.
        from ai.services import run_risk_checks

        flags = run_risk_checks(valuation, stage=stage)["flags"]
        review, _ = StageReview.objects.get_or_create(
            valuation=valuation, stage=stage, defaults={"ai_flags": flags}
        )
        review.ai_flags = flags
        return review

    def post(self, request, valuation_id, stage, action):
        if stage not in Stage.values:
            return Response({"detail": "Unknown stage."}, status=status.HTTP_400_BAD_REQUEST)
        valuation = get_object_or_404(Valuation, id=valuation_id)
        review = self._get_review(valuation, stage)

        if action == "approve":
            review.status = ReviewStatus.APPROVED
            review.actor = request.user
            review.reason = ""
            review.acted_at = timezone.now()
            review.save()
            # Advance the case status.
            if stage == Stage.FINAL_APPROVAL:
                valuation.status = ValuationStatus.APPROVED
            else:
                valuation.status = ValuationStatus.IN_VERIFICATION
            valuation.save(update_fields=["status", "updated_at"])
            return Response(StageReviewSerializer(review).data)

        if action == "revert":
            payload = RevertSerializer(data=request.data)
            payload.is_valid(raise_exception=True)
            review.status = ReviewStatus.REVERTED
            review.actor = request.user
            review.reason = payload.validated_data["reason"]
            review.acted_at = timezone.now()
            review.save()
            valuation.status = ValuationStatus.REVERTED
            valuation.save(update_fields=["status", "updated_at"])
            return Response(StageReviewSerializer(review).data)

        return Response({"detail": "Unknown action."}, status=status.HTTP_400_BAD_REQUEST)
