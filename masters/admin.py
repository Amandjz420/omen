"""Admin registration for master data."""

from django.contrib import admin

from .models import (
    Bank,
    BankReportHeading,
    ClientDesignation,
    ClientDivision,
    DetailCategory,
    Orderer,
    Question,
    ReportSetup,
    ServiceSubType,
    ServiceType,
)


@admin.register(ServiceType)
class ServiceTypeAdmin(admin.ModelAdmin):
    list_display = ("name", "code", "is_active")
    search_fields = ("name", "code")


@admin.register(ServiceSubType)
class ServiceSubTypeAdmin(admin.ModelAdmin):
    list_display = ("name", "service_type", "code", "is_active")
    list_filter = ("service_type",)


@admin.register(Bank)
class BankAdmin(admin.ModelAdmin):
    list_display = ("name", "kind", "code", "is_active")
    list_filter = ("kind", "is_active")
    search_fields = ("name", "code")


@admin.register(Orderer)
class OrdererAdmin(admin.ModelAdmin):
    list_display = ("name", "bank", "designation", "email")
    list_filter = ("bank",)
    search_fields = ("name", "email")


@admin.register(DetailCategory)
class DetailCategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "code", "sequence")


@admin.register(Question)
class QuestionAdmin(admin.ModelAdmin):
    list_display = (
        "text",
        "service_type",
        "sub_type",
        "detail_category",
        "answer_type",
        "sequence",
        "is_mandatory",
    )
    list_filter = ("service_type", "sub_type", "answer_type", "is_mandatory")
    search_fields = ("text",)


@admin.register(BankReportHeading)
class BankReportHeadingAdmin(admin.ModelAdmin):
    list_display = ("title", "bank", "sequence")
    list_filter = ("bank",)


@admin.register(ReportSetup)
class ReportSetupAdmin(admin.ModelAdmin):
    list_display = ("bank", "service_type", "sub_type", "question", "heading", "sequence")
    list_filter = ("bank", "service_type")


admin.site.register(ClientDivision)
admin.site.register(ClientDesignation)
