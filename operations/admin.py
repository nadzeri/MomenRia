from datetime import timedelta

from django.contrib import admin
from django.db.models import Count
from django.utils import timezone

from momenria.admin import AuditedAdmin, ReadOnlyAdmin

from .models import AccountAccessRequest, AnalyticsEvent, AuditEvent, BenchmarkEvidence, DecisionRecord, DeletionTask, OperationalAlert, OutboxEvent, RateLimitBucket, SupportGrant, SupportReply, SupportTicket


class SupportReplyInline(admin.TabularInline):
    model = SupportReply
    fields = ("message", "created_at")
    readonly_fields = fields
    extra = 0
    can_delete = False

    def has_add_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return False


@admin.register(SupportTicket)
class SupportTicketAdmin(AuditedAdmin):
    list_display = ("subject", "owner", "status", "updated_at")
    list_filter = ("status", "updated_at")
    search_fields = ("subject", "owner__email", "message", "messages__message")
    readonly_fields = ("id", "owner", "project", "order", "subject", "message", "created_at", "updated_at")
    inlines = (SupportReplyInline,)

    def has_add_permission(self, request):
        return False


@admin.register(AccountAccessRequest)
class AccountAccessRequestAdmin(AuditedAdmin):
    list_display = ("subject", "email", "status", "created_at")
    list_filter = ("status", "created_at")
    search_fields = ("email", "subject", "message")
    readonly_fields = ("id", "email", "subject", "message", "created_at", "updated_at")

    def has_add_permission(self, request):
        return False


@admin.register(AnalyticsEvent)
class AnalyticsEventAdmin(ReadOnlyAdmin):
    list_display = ("event", "project_id", "job_id", "result_id", "order_id", "created_at")
    list_filter = ("event", "created_at")
    change_list_template = "admin/operations/analyticsevent/change_list.html"

    def changelist_view(self, request, extra_context=None):
        since = timezone.now() - timedelta(days=90)
        metrics = AnalyticsEvent.objects.filter(created_at__gte=since).values("event").annotate(count=Count("id")).order_by("event")
        return super().changelist_view(request, {**(extra_context or {}), "metrics": metrics, "metrics_since": since})


for model in (AuditEvent, DeletionTask, OperationalAlert, OutboxEvent, RateLimitBucket, SupportReply):
    admin.site.register(model, ReadOnlyAdmin)

for model in (BenchmarkEvidence, DecisionRecord, SupportGrant):
    admin.site.register(model, AuditedAdmin)
