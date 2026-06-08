"""Admin registration for leads and work orders."""

from django.contrib import admin

from .models import Lead, WorkOrder


@admin.register(Lead)
class LeadAdmin(admin.ModelAdmin):
    list_display = ("title", "bank", "status", "created_by", "created_at")
    list_filter = ("status", "bank")
    search_fields = ("title", "contact_name")


@admin.register(WorkOrder)
class WorkOrderAdmin(admin.ModelAdmin):
    list_display = ("reference", "bank", "service_type", "sub_type", "status")
    list_filter = ("status", "bank", "service_type")
    search_fields = ("reference",)
