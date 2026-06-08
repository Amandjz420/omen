"""Admin registration for valuation case data."""

from django.contrib import admin

from .models import Answer, MarketRateLookup, MediaAsset, Valuation


class MediaAssetInline(admin.TabularInline):
    model = MediaAsset
    extra = 0
    fields = ("kind", "filename", "uploaded", "mime")


class AnswerInline(admin.TabularInline):
    model = Answer
    extra = 0
    fields = ("question", "value", "confidence", "confirmed", "ai_filled")


@admin.register(Valuation)
class ValuationAdmin(admin.ModelAdmin):
    list_display = ("id", "work_order", "status", "assigned_valuer", "locality")
    list_filter = ("status",)
    inlines = [MediaAssetInline, AnswerInline]


@admin.register(MediaAsset)
class MediaAssetAdmin(admin.ModelAdmin):
    list_display = ("kind", "filename", "valuation", "uploaded", "created_at")
    list_filter = ("kind", "uploaded")


@admin.register(Answer)
class AnswerAdmin(admin.ModelAdmin):
    list_display = ("question", "valuation", "confidence", "confirmed", "ai_filled")
    list_filter = ("confidence", "confirmed", "ai_filled")


@admin.register(MarketRateLookup)
class MarketRateLookupAdmin(admin.ModelAdmin):
    list_display = ("valuation", "query", "created_at")
