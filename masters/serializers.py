"""Serializers for master/config data."""

from __future__ import annotations

from rest_framework import serializers

from .models import (
    Bank,
    Orderer,
    Question,
    ServiceSubType,
    ServiceType,
)


class ServiceTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = ServiceType
        fields = ("id", "name", "code", "description", "is_active")


class ServiceSubTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = ServiceSubType
        fields = ("id", "service_type", "name", "code", "is_active")


class BankSerializer(serializers.ModelSerializer):
    class Meta:
        model = Bank
        fields = ("id", "name", "kind", "code", "is_active")


class OrdererSerializer(serializers.ModelSerializer):
    class Meta:
        model = Orderer
        fields = ("id", "bank", "division", "designation", "name", "email", "phone")


class QuestionSerializer(serializers.ModelSerializer):
    """A rendered Question Bank entry, including the section it belongs to."""

    detail_category_name = serializers.CharField(
        source="detail_category.name", read_only=True
    )
    detail_category_sequence = serializers.IntegerField(
        source="detail_category.sequence", read_only=True
    )

    class Meta:
        model = Question
        fields = (
            "id",
            "text",
            "service_type",
            "sub_type",
            "detail_category",
            "detail_category_name",
            "detail_category_sequence",
            "answer_type",
            "options",
            "sequence",
            "is_mandatory",
            "bank",
        )
