"""Master-data routes (mounted under /api/)."""

from rest_framework.routers import DefaultRouter

from .views import (
    BankViewSet,
    OrdererViewSet,
    QuestionTemplateViewSet,
    ServiceSubTypeViewSet,
    ServiceTypeViewSet,
)

router = DefaultRouter(trailing_slash=False)
router.register("service-types", ServiceTypeViewSet, basename="service-type")
router.register("service-subtypes", ServiceSubTypeViewSet, basename="service-subtype")
router.register("banks", BankViewSet, basename="bank")
router.register("orderers", OrdererViewSet, basename="orderer")
router.register("questions", QuestionTemplateViewSet, basename="question")

urlpatterns = router.urls
