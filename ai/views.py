"""AI job polling endpoint."""

from __future__ import annotations

from rest_framework import mixins, viewsets
from rest_framework.permissions import IsAuthenticated

from .models import AIJob
from .serializers import AIJobSerializer


class AIJobViewSet(mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    """``GET /api/jobs/{id}`` → ``{status, result, error}`` (plus metadata)."""

    serializer_class = AIJobSerializer
    permission_classes = [IsAuthenticated]
    queryset = AIJob.objects.all()

    def get_queryset(self):
        user = self.request.user
        qs = AIJob.objects.select_related("valuation")
        if getattr(user, "role", None) == "valuer":
            return qs.filter(valuation__assigned_valuer=user)
        return qs
