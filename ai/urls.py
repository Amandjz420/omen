"""AI routes (mounted under /api/). The AI *action* endpoints live in
``valuations.urls`` since they hang off a valuation."""

from rest_framework.routers import DefaultRouter

from .views import AIJobViewSet

router = DefaultRouter(trailing_slash=False)
router.register("jobs", AIJobViewSet, basename="job")

urlpatterns = router.urls
