"""Valuation, media and answer endpoints."""

from __future__ import annotations

from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from ai.jobs import enqueue
from leads.models import WorkOrder

from . import storage
from .models import (
    Answer,
    Confidence,
    MediaAsset,
    Valuation,
    ValuationStatus,
)
from .serializers import (
    AnswerPatchSerializer,
    AnswerSerializer,
    GeoSerializer,
    MarketRateLookupSerializer,
    MediaAssetSerializer,
    ValuationCreateSerializer,
    ValuationDetailSerializer,
    ValuationListSerializer,
)


class ValuationViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    """Valuations assigned to the requester, plus per-case actions."""

    permission_classes = [IsAuthenticated]
    filterset_fields = ("status",)

    def get_queryset(self):
        user = self.request.user
        qs = Valuation.objects.select_related(
            "work_order",
            "work_order__bank",
            "work_order__service_type",
            "work_order__sub_type",
        )
        # Valuers see only their cases; verifiers/admin/office see all.
        if getattr(user, "role", None) == "valuer":
            qs = qs.filter(assigned_valuer=user)
        return qs

    def get_serializer_class(self):
        if self.action == "retrieve":
            return ValuationDetailSerializer
        if self.action == "create":
            return ValuationCreateSerializer
        return ValuationListSerializer

    @extend_schema(request=ValuationCreateSerializer, responses=ValuationListSerializer)
    def create(self, request, *args, **kwargs):
        """``POST /api/valuations`` — create from a ``work_order_id``."""
        serializer = ValuationCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        wo = get_object_or_404(WorkOrder, id=serializer.validated_data["work_order_id"])
        if hasattr(wo, "valuation"):
            return Response(
                {"detail": "A valuation already exists for this work order."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        valuation = Valuation.objects.create(
            work_order=wo,
            assigned_valuer=(
                request.user if getattr(request.user, "role", None) == "valuer" else None
            ),
            address=wo.property_address,
            status=ValuationStatus.IN_PROGRESS,
        )
        return Response(
            ValuationListSerializer(valuation).data, status=status.HTTP_201_CREATED
        )

    # --- Geo --------------------------------------------------------------
    @extend_schema(request=GeoSerializer, responses=ValuationListSerializer)
    @action(detail=True, methods=["post"])
    def geo(self, request, pk=None):
        """``POST /api/valuations/{id}/geo`` → set coordinates."""
        valuation = self.get_object()
        serializer = GeoSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        valuation.latitude = serializer.validated_data["lat"]
        valuation.longitude = serializer.validated_data["lng"]
        valuation.save(update_fields=["latitude", "longitude", "updated_at"])
        return Response(ValuationListSerializer(valuation).data)

    # --- Submit -----------------------------------------------------------
    @action(detail=True, methods=["post"])
    def submit(self, request, pk=None):
        """``POST /api/valuations/{id}/submit`` → move to verification.

        Blocked if any mandatory answer is still ``red``.
        """
        valuation = self.get_object()
        red_mandatory = valuation.answers.filter(
            question__is_mandatory=True, confidence=Confidence.RED
        ).count()
        if red_mandatory:
            return Response(
                {
                    "detail": f"{red_mandatory} mandatory answer(s) still red; "
                    "resolve them before submitting."
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        valuation.status = ValuationStatus.SUBMITTED
        valuation.save(update_fields=["status", "updated_at"])
        return Response({"status": valuation.status})

    # --- Media list -------------------------------------------------------
    @extend_schema(responses=MediaAssetSerializer(many=True))
    @action(detail=True, methods=["get"])
    def media(self, request, pk=None):
        """``GET /api/valuations/{id}/media`` → assets with presigned GET URLs."""
        valuation = self.get_object()
        assets = valuation.media_assets.all()
        return Response(MediaAssetSerializer(assets, many=True).data)

    # --- Answers ----------------------------------------------------------
    @extend_schema(responses=AnswerSerializer(many=True))
    @action(detail=True, methods=["get"])
    def answers(self, request, pk=None):
        """``GET /api/valuations/{id}/answers``."""
        valuation = self.get_object()
        qs = valuation.answers.select_related("question").all()
        return Response(AnswerSerializer(qs, many=True).data)

    @extend_schema(responses=MarketRateLookupSerializer(many=True))
    @action(detail=True, methods=["get"], url_path="market-rates")
    def market_rates(self, request, pk=None):
        """``GET /api/valuations/{id}/market-rates`` → stored lookups."""
        valuation = self.get_object()
        return Response(
            MarketRateLookupSerializer(valuation.market_rates.all(), many=True).data
        )

    # --- AI actions (each enqueues a job) --------------------------------
    def _enqueue(self, valuation, task):
        job = enqueue(valuation, task)
        return Response({"job_id": str(job.id)}, status=status.HTTP_202_ACCEPTED)

    @action(detail=True, methods=["post"])
    def transcribe(self, request, pk=None):
        return self._enqueue(self.get_object(), "transcribe")

    @action(detail=True, methods=["post"], url_path="extract-documents")
    def extract_documents(self, request, pk=None):
        return self._enqueue(self.get_object(), "extract-documents")

    @action(detail=True, methods=["post"], url_path="analyze-photos")
    def analyze_photos(self, request, pk=None):
        return self._enqueue(self.get_object(), "analyze-photos")

    @action(detail=True, methods=["post"])
    def autofill(self, request, pk=None):
        return self._enqueue(self.get_object(), "autofill")

    @action(detail=True, methods=["post"], url_path="market-rate")
    def market_rate(self, request, pk=None):
        return self._enqueue(self.get_object(), "market-rate")

    @action(detail=True, methods=["post"], url_path="draft-comments")
    def draft_comments(self, request, pk=None):
        return self._enqueue(self.get_object(), "draft-comments")

    @action(detail=True, methods=["post"], url_path="generate-report")
    def generate_report(self, request, pk=None):
        return self._enqueue(self.get_object(), "generate-report")

    # --- Report URL -------------------------------------------------------
    @action(detail=True, methods=["get"])
    def report(self, request, pk=None):
        """``GET /api/valuations/{id}/report`` → presigned PDF URL (latest)."""
        valuation = self.get_object()
        key = f"valuations/{valuation.id}/report/valuation_report.pdf"
        return Response({"url": storage.presign_get(key)})


class AnswerViewSet(mixins.UpdateModelMixin, viewsets.GenericViewSet):
    """``PATCH /api/answers/{id}`` — valuer edits/confirms an answer."""

    serializer_class = AnswerSerializer
    permission_classes = [IsAuthenticated]
    http_method_names = ["patch"]

    def get_queryset(self):
        user = self.request.user
        qs = Answer.objects.select_related("question", "valuation")
        if getattr(user, "role", None) == "valuer":
            qs = qs.filter(valuation__assigned_valuer=user)
        return qs

    @extend_schema(request=AnswerPatchSerializer, responses=AnswerSerializer)
    def partial_update(self, request, *args, **kwargs):
        answer = self.get_object()
        patch = AnswerPatchSerializer(data=request.data)
        patch.is_valid(raise_exception=True)
        data = patch.validated_data

        fields = ["updated_at"]
        if "value" in data:
            answer.value = data["value"]
            fields.append("value")
        if data.get("confirmed"):
            answer.confirmed = True
            fields.append("confirmed")
            # A valuer-confirmed, non-empty answer is no longer "red".
            if (
                answer.value not in (None, "", [], {})
                and answer.confidence == Confidence.RED
            ):
                answer.confidence = Confidence.GREEN
                fields.append("confidence")
        elif "confirmed" in data:
            answer.confirmed = False
            fields.append("confirmed")

        answer.save(update_fields=fields)
        return Response(AnswerSerializer(answer).data)


class MediaPresignView(APIView):
    """``POST /api/media/presign`` → presigned S3 PUT for a direct upload."""

    permission_classes = [IsAuthenticated]

    def post(self, request):
        data = request.data
        valuation = get_object_or_404(Valuation, id=data.get("valuation_id"))
        kind = data["kind"]
        mime = data.get("mime", "application/octet-stream")
        filename = data.get("filename", "file")
        key = storage.build_key(valuation.id, kind, filename)
        asset = MediaAsset.objects.create(
            valuation=valuation, kind=kind, s3_key=key, mime=mime, filename=filename
        )
        presigned = storage.presign_put(key, mime)
        return Response(
            {
                "asset_id": str(asset.id),
                "upload_url": presigned["upload_url"],
                "headers": presigned["headers"],
            }
        )


class MediaConfirmView(APIView):
    """``POST /api/media/confirm`` → mark an upload complete, attach geo."""

    permission_classes = [IsAuthenticated]

    def post(self, request):
        data = request.data
        asset = get_object_or_404(MediaAsset, id=data.get("asset_id"))
        asset.uploaded = True
        fields = ["uploaded", "updated_at"]
        for attr, key in (("size", "size"), ("duration", "duration")):
            if data.get(key) is not None:
                setattr(asset, attr, data[key])
                fields.append(attr)
        if data.get("lat") is not None:
            asset.latitude = data["lat"]
            fields.append("latitude")
        if data.get("lng") is not None:
            asset.longitude = data["lng"]
            fields.append("longitude")
        asset.save(update_fields=fields)
        return Response(MediaAssetSerializer(asset).data)
