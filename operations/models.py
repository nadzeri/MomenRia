import uuid

from django.conf import settings
from django.db import models


class AuditEvent(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT, related_name="audit_events")
    action = models.CharField(max_length=100)
    object_type = models.CharField(max_length=80)
    object_id = models.UUIDField(null=True, blank=True)
    reason = models.CharField(max_length=500, blank=True)
    metadata = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [models.Index(fields=("object_type", "object_id")), models.Index(fields=("created_at",))]


class AnalyticsEvent(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    event_id = models.UUIDField(unique=True)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT, related_name="analytics_events")
    project_id = models.UUIDField(null=True, blank=True)
    job_id = models.UUIDField(null=True, blank=True)
    result_id = models.UUIDField(null=True, blank=True)
    order_id = models.UUIDField(null=True, blank=True)
    event = models.CharField(max_length=80)
    dimensions = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [models.Index(fields=("event", "created_at"))]


class OutboxEvent(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    topic = models.CharField(max_length=100)
    payload = models.JSONField()
    created_at = models.DateTimeField(auto_now_add=True)
    delivered_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        indexes = [models.Index(fields=("delivered_at", "created_at"))]


class SupportTicket(models.Model):
    class Status(models.TextChoices):
        WAITING = "waiting", "Waiting"
        ACTION_REQUIRED = "action_required", "Action required"
        RESOLVED = "resolved", "Resolved"
        REFUND_PROGRESS = "refund_progress", "Refund progress"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="support_tickets")
    project = models.ForeignKey("projects.Project", null=True, blank=True, on_delete=models.SET_NULL, related_name="support_tickets")
    order = models.ForeignKey("commerce.Order", null=True, blank=True, on_delete=models.SET_NULL, related_name="support_tickets")
    subject = models.CharField(max_length=120)
    message = models.CharField(max_length=2000)
    status = models.CharField(max_length=24, choices=Status.choices, default=Status.WAITING)
    owner_visible_reply = models.CharField(max_length=2000, blank=True)
    operator_minutes = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


class SupportReply(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    ticket = models.ForeignKey(SupportTicket, on_delete=models.PROTECT, related_name="messages")
    message = models.CharField(max_length=2000)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("created_at", "id")

    def save(self, *args, **kwargs):
        prior = type(self).objects.filter(pk=self.pk).first() if self.pk else None
        if prior and any(getattr(prior, field) != getattr(self, field) for field in ("ticket_id", "message", "created_at")):
            raise ValueError("Owner support replies are immutable")
        return super().save(*args, **kwargs)


class AccountAccessRequest(models.Model):
    class Status(models.TextChoices):
        WAITING = "waiting", "Waiting"
        RESOLVED = "resolved", "Resolved"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    email = models.EmailField(max_length=254)
    subject = models.CharField(max_length=120)
    message = models.CharField(max_length=2000)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.WAITING)
    operator_notes = models.CharField(max_length=2000, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-created_at", "-id")


class SupportGrant(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="support_grants")
    project = models.ForeignKey("projects.Project", on_delete=models.PROTECT, related_name="support_grants")
    staff = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT, related_name="received_support_grants")
    staff_role = models.CharField(max_length=80, default="support")
    purpose = models.CharField(max_length=500)
    granted_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    revoked_at = models.DateTimeField(null=True, blank=True)


class DeletionTask(models.Model):
    class State(models.TextChoices):
        QUEUED = "queued", "Queued"
        RUNNING = "running", "Running"
        COMPLETE = "complete", "Complete"
        FAILED = "failed", "Failed"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    project_id_snapshot = models.UUIDField()
    deletion_epoch = models.PositiveIntegerField()
    state = models.CharField(max_length=16, choices=State.choices, default=State.QUEUED)
    attempts = models.PositiveSmallIntegerField(default=0)
    next_run_at = models.DateTimeField()
    error_code = models.CharField(max_length=80, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        indexes = [models.Index(fields=("state", "next_run_at"))]


class DecisionRecord(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    decision_id = models.CharField(max_length=20)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="decision_records")
    value = models.TextField()
    evidence = models.TextField(blank=True)
    policy_version = models.CharField(max_length=40)
    affected_requirements = models.JSONField(default=list)
    effective_at = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=("decision_id", "policy_version"), name="operations_decision_policy_unique")]


class BenchmarkEvidence(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    template = models.ForeignKey("catalog.TemplateVersion", on_delete=models.PROTECT, related_name="benchmark_evidence")
    configuration_hash = models.CharField(max_length=64)
    people_count = models.PositiveSmallIntegerField()
    attempts = models.PositiveIntegerField()
    accepted_first = models.PositiveIntegerField()
    accepted_within_allowance = models.PositiveIntegerField()
    technical_failures = models.PositiveIntegerField()
    missing_feedback = models.PositiveIntegerField()
    evidence_uri = models.CharField(max_length=500)
    approved = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)


class RateLimitBucket(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    action = models.CharField(max_length=40)
    identifier_hash = models.CharField(max_length=64)
    window_start = models.DateTimeField()
    count = models.PositiveIntegerField(default=0)

    class Meta:
        constraints = [models.UniqueConstraint(fields=("action", "identifier_hash", "window_start"), name="operations_rate_limit_bucket_unique")]
        indexes = [models.Index(fields=("window_start",))]


class OperationalAlert(models.Model):
    class Severity(models.TextChoices):
        WARNING = "warning", "Warning"
        CRITICAL = "critical", "Critical"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    code = models.CharField(max_length=80, unique=True)
    severity = models.CharField(max_length=16, choices=Severity.choices)
    active = models.BooleanField(default=True)
    message = models.CharField(max_length=500)
    details = models.JSONField(default=dict)
    opened_at = models.DateTimeField(auto_now_add=True)
    last_seen_at = models.DateTimeField(auto_now=True)
    resolved_at = models.DateTimeField(null=True, blank=True)
