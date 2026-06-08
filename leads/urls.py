"""Lead / work-order routes (mounted under /api/)."""

from rest_framework.routers import DefaultRouter

from .views import LeadViewSet, WorkOrderViewSet

router = DefaultRouter(trailing_slash=False)
router.register("leads", LeadViewSet, basename="lead")
router.register("work-orders", WorkOrderViewSet, basename="work-order")

urlpatterns = router.urls
