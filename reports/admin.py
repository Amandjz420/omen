"""Admin registration for report stub models."""

from django.contrib import admin

from .models import Dispatch, Invoice, PayInReceipt

admin.site.register(Invoice)
admin.site.register(Dispatch)
admin.site.register(PayInReceipt)
