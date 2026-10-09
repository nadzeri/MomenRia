from django.contrib import admin

from momenria.admin import ReadOnlyAdmin

from .models import Entitlement, Order, PaymentEvent, Refund


for model in (Order, PaymentEvent, Entitlement, Refund):
    admin.site.register(model, ReadOnlyAdmin)
