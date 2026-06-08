"""Serializers for valuations, media, answers and market-rate lookups."""

from __future__ import annotations

from rest_framework import serializers

from masters.serializers import QuestionSerializer

from . import storage
from .models import Answer, MarketRateLookup, MediaAsset, Valuation


class MediaAssetSerializer(serializers.ModelSerializer):
    """A media asset, with a presigned GET URL for download."""

    download_url = serializers.SerializerMethodField()

    class Meta:
        model = MediaAsset
        fields = (
            "id",
            "valuation",
            "kind",
            "s3_key",
            "mime",
            "filename",
            "size",
            "duration",
            "latitude",
            "longitude",
            "uploaded",
            "transcript",
            "extraction",
            "download_url",
            "created_at",
        )
        read_only_fields = ("s3_key", "uploaded", "transcript", "extraction")

    def get_download_url(self, obj: MediaAsset) -> str | None:
        if not obj.uploaded:
            return None
        request = self.context.get("request")
        return storage.presign_get(obj.s3_key, request=request)


class AnswerSerializer(serializers.ModelSerializer):
    question_text = serializers.CharField(source="question.text", read_only=True)
    answer_type = serializers.CharField(source="question.answer_type", read_only=True)

    class Meta:
        model = Answer
        fields = (
            "id",
            "valuation",
            "question",
            "question_text",
            "answer_type",
            "value",
            "confidence",
            "confirmed",
            "evidence",
            "ai_filled",
            "updated_at",
        )
        read_only_fields = (
            "valuation",
            "question",
            "confidence",
            "evidence",
            "ai_filled",
        )


class AnswerPatchSerializer(serializers.Serializer):
    """Valuer edit/confirm payload for ``PATCH /api/answers/{id}``."""

    value = serializers.JSONField(required=False)
    confirmed = serializers.BooleanField(required=False)


class MarketRateLookupSerializer(serializers.ModelSerializer):
    class Meta:
        model = MarketRateLookup
        fields = ("id", "valuation", "query", "result_range", "citations", "created_at")


class ValuationListSerializer(serializers.ModelSerializer):
    work_order_reference = serializers.CharField(
        source="work_order.reference", read_only=True
    )
    bank_name = serializers.CharField(source="work_order.bank.name", read_only=True)

    class Meta:
        model = Valuation
        fields = (
            "id",
            "work_order",
            "work_order_reference",
            "bank_name",
            "status",
            "assigned_valuer",
            "latitude",
            "longitude",
            "address",
            "locality",
            "created_at",
        )


class ValuationCreateSerializer(serializers.Serializer):
    """``POST /api/valuations`` — create from a work order."""

    work_order_id = serializers.UUIDField()


class GeoSerializer(serializers.Serializer):
    """``POST /api/valuations/{id}/geo``."""

    lat = serializers.DecimalField(max_digits=9, decimal_places=6)
    lng = serializers.DecimalField(max_digits=9, decimal_places=6)


class MergedAnswerSerializer(serializers.Serializer):
    """A question merged with its current answer for the case detail view."""

    question = QuestionSerializer()
    answer = AnswerSerializer(allow_null=True)


class ValuationDetailSerializer(serializers.ModelSerializer):
    """Case header + GPS + the question set merged with current answers."""

    work_order = serializers.SerializerMethodField()
    questions = serializers.SerializerMethodField()

    class Meta:
        model = Valuation
        fields = (
            "id",
            "status",
            "assigned_valuer",
            "latitude",
            "longitude",
            "address",
            "locality",
            "work_order",
            "questions",
            "created_at",
        )

    def get_work_order(self, obj: Valuation) -> dict:
        wo = obj.work_order
        return {
            "id": str(wo.id),
            "reference": wo.reference,
            "bank": {"id": str(wo.bank_id), "name": wo.bank.name},
            "service_type": {"id": str(wo.service_type_id), "name": wo.service_type.name},
            "sub_type": (
                {"id": str(wo.sub_type_id), "name": wo.sub_type.name}
                if wo.sub_type_id
                else None
            ),
            "property_address": wo.property_address,
        }

    def get_questions(self, obj: Valuation) -> list[dict]:
        from masters.selectors import questions_for

        wo = obj.work_order
        questions = questions_for(
            service_type_id=wo.service_type_id,
            sub_type_id=wo.sub_type_id,
            bank_id=wo.bank_id,
        )
        answers = {a.question_id: a for a in obj.answers.all()}
        merged = []
        for q in questions:
            ans = answers.get(q.id)
            merged.append(
                {
                    "question": QuestionSerializer(q).data,
                    "answer": AnswerSerializer(ans).data if ans else None,
                }
            )
        return merged
