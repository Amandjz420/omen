"""Read-mostly endpoints for master data + the rendered question template."""

from __future__ import annotations

from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import mixins, viewsets
from rest_framework.permissions import IsAuthenticated

from .models import Bank, Orderer, ServiceSubType, ServiceType
from .selectors import questions_for
from .serializers import (
    BankSerializer,
    OrdererSerializer,
    QuestionSerializer,
    ServiceSubTypeSerializer,
    ServiceTypeSerializer,
)


class ServiceTypeViewSet(mixins.ListModelMixin, viewsets.GenericViewSet):
    """``GET /api/service-types``."""

    queryset = ServiceType.objects.filter(is_active=True)
    serializer_class = ServiceTypeSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = None


class ServiceSubTypeViewSet(mixins.ListModelMixin, viewsets.GenericViewSet):
    """``GET /api/service-subtypes?service_type=``."""

    serializer_class = ServiceSubTypeSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = None

    def get_queryset(self):
        qs = ServiceSubType.objects.filter(is_active=True)
        service_type = self.request.query_params.get("service_type")
        if service_type:
            qs = qs.filter(service_type_id=service_type)
        return qs


class BankViewSet(mixins.ListModelMixin, viewsets.GenericViewSet):
    """``GET /api/banks``."""

    queryset = Bank.objects.filter(is_active=True)
    serializer_class = BankSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = None


class OrdererViewSet(mixins.ListModelMixin, viewsets.GenericViewSet):
    """``GET /api/orderers?bank=``."""

    serializer_class = OrdererSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = None

    def get_queryset(self):
        qs = Orderer.objects.select_related("bank")
        bank = self.request.query_params.get("bank")
        if bank:
            qs = qs.filter(bank_id=bank)
        return qs


class QuestionTemplateViewSet(mixins.ListModelMixin, viewsets.GenericViewSet):
    """``GET /api/questions?service_type=&sub_type=&bank=``.

    Returns the rendered template: the ordered Question set that applies to a
    case (service type + optional sub-type + optional bank scope).
    """

    serializer_class = QuestionSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = None

    @extend_schema(
        parameters=[
            OpenApiParameter("service_type", str, required=True),
            OpenApiParameter("sub_type", str, required=False),
            OpenApiParameter("bank", str, required=False),
        ]
    )
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    def get_queryset(self):
        params = self.request.query_params
        service_type = params.get("service_type")
        if not service_type:
            return self.serializer_class.Meta.model.objects.none()
        return questions_for(
            service_type_id=service_type,
            sub_type_id=params.get("sub_type"),
            bank_id=params.get("bank"),
        )
