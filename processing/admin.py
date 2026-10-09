from django.contrib import admin

from momenria.admin import AuditedAdmin, ReadOnlyAdmin

from .models import AdmissionControl, Allowance, AllowanceReservation, BudgetReservation, BudgetWindow, CostEntry, IdempotencyRecord, Job, JobAttempt, WorkerControl


class JobAdmin(ReadOnlyAdmin):
    exclude = ("input_snapshot",)


admin.site.register(Job, JobAdmin)


class AdmissionControlAdmin(AuditedAdmin):
    exclude = ("updated_by",)

    def save_model(self, request, obj, form, change):
        obj.updated_by = request.user
        super().save_model(request, obj, form, change)


admin.site.register(AdmissionControl, AdmissionControlAdmin)

for model in (Allowance, AllowanceReservation, BudgetReservation, BudgetWindow, CostEntry, IdempotencyRecord, JobAttempt, WorkerControl):
    admin.site.register(model, ReadOnlyAdmin)
