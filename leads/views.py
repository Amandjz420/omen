"""Lead and work-order endpoints."""

from __future__ import annotations

from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated

from .models import Lead, WorkOrder
from .serializers import LeadSerializer, WorkOrderSerializer


class LeadViewSet(viewsets.ModelViewSet):
    """``GET/POST /api/leads`` and detail routes."""

    queryset = Lead.objects.select_related("bank").all()
    serializer_class = LeadSerializer
    permission_classes = [IsAuthenticated]

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)


class WorkOrderViewSet(viewsets.ModelViewSet):
    """``GET/POST /api/work-orders`` and ``GET /api/work-orders/{id}``."""

    queryset = WorkOrder.objects.select_related(
        "bank", "orderer", "service_type", "sub_type"
    ).all()
    serializer_class = WorkOrderSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ("status", "bank", "service_type")
