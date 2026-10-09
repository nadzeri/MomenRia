import uuid

from django.conf import settings
from django.db import models
from django.db.models import Q


class Allowance(models.Model):
    class Kind(models.TextChoices):
        CREATION = "creation", "Creation"
        CORRECTION = "correction", "Correction"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="allowances")
    project = models.ForeignKey("projects.Project", null=True, blank=True, on_delete=models.PROTECT, related_name="allowances")
    kind = models.CharField(max_length=16, choices=Kind.choices)
    policy_version = models.CharField(max_length=40)
    consumed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=("owner", "kind"), condition=Q(kind="creation"), name="processing_one_creation_allowance"),
            models.UniqueConstraint(fields=("project", "kind"), condition=Q(kind="correction"), name="processing_one_correction_allowance"),
        ]


class Job(models.Model):
    class Operation(models.TextChoices):
        CREATION = "creation", "Creation"
        CORRECTION = "correction", "Correction"
        CHARACTER_SHEET = "character_sheet", "Character sheet"

    class State(models.TextChoices):
        QUEUED = "queued", "Queued"
        DISPATCHING = "dispatching", "Dispatching"
        PROCESSING = "processing", "Processing"
        UNCERTAIN = "uncertain", "Uncertain"
        FINALIZING = "finalizing", "Finalizing"
        READY = "ready", "Ready"
        FAILED = "failed", "Failed"
        CANCELLED = "cancelled", "Cancelled"

    ACTIVE_STATES = (State.QUEUED, State.DISPATCHING, State.PROCESSING, State.UNCERTAIN, State.FINALIZING)

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="jobs")
    project = models.ForeignKey("projects.Project", on_delete=models.PROTECT, related_name="jobs")
    allowance = models.ForeignKey(Allowance, null=True, blank=True, on_delete=models.PROTECT, related_name="jobs")
    character_sheet = models.OneToOneField("projects.CharacterSheet", null=True, blank=True, on_delete=models.PROTECT, related_name="preparation_job")
    parent_result = models.ForeignKey("projects.ResultVersion", null=True, blank=True, on_delete=models.PROTECT, related_name="correction_jobs")
    target_slot = models.ForeignKey("catalog.FaceSlot", null=True, blank=True, on_delete=models.PROTECT, related_name="jobs")
    result = models.OneToOneField("projects.ResultVersion", null=True, blank=True, on_delete=models.PROTECT, related_name="job")
    operation = models.CharField(max_length=16, choices=Operation.choices)
    state = models.CharField(max_length=16, choices=State.choices, default=State.QUEUED)
    input_snapshot = models.JSONField()
    deletion_epoch = models.PositiveIntegerField()
    estimated_cost_idr = models.PositiveIntegerField()
    lease_token = models.UUIDField(null=True, blank=True)
    fencing_token = models.PositiveIntegerField(default=0)
    leased_until = models.DateTimeField(null=True, blank=True)
    heartbeat_at = models.DateTimeField(null=True, blank=True)
    next_run_at = models.DateTimeField()
    error_code = models.CharField(max_length=80, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=("project",), condition=Q(state__in=("queued", "dispatching", "processing", "uncertain", "finalizing")), name="processing_one_active_job_per_project"),
            models.CheckConstraint(condition=Q(operation="character_sheet", allowance__isnull=True, character_sheet__isnull=False, result__isnull=True) | Q(operation__in=("creation", "correction"), character_sheet__isnull=True), name="processing_operation_allowance_sheet"),
        ]
        indexes = [models.Index(fields=("state", "next_run_at")), models.Index(fields=("leased_until",))]


class JobAttempt(models.Model):
    class State(models.TextChoices):
        PREPARED = "prepared", "Prepared"
        SENT = "sent", "Sent"
        SUCCEEDED = "succeeded", "Succeeded"
        FAILED = "failed", "Failed"
        UNCERTAIN = "uncertain", "Uncertain"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    job = models.ForeignKey(Job, on_delete=models.PROTECT, related_name="attempts")
    number = models.PositiveSmallIntegerField()
    state = models.CharField(max_length=16, choices=State.choices, default=State.PREPARED)
    provider_request_id = models.CharField(max_length=180, blank=True)
    provider_completed = models.BooleanField(default=False)
    actual_model = models.CharField(max_length=180, blank=True)
    error_code = models.CharField(max_length=80, blank=True)
    started_at = models.DateTimeField(auto_now_add=True)
    finished_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=("job", "number"), name="processing_attempt_number_unique")]


class BudgetReservation(models.Model):
    class State(models.TextChoices):
        RESERVED = "reserved", "Reserved"
        RECONCILED = "reconciled", "Reconciled"
        RELEASED = "released", "Released"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    job = models.OneToOneField(Job, on_delete=models.PROTECT, related_name="budget_reservation")
    scope = models.CharField(max_length=40)
    period = models.DateField()
    currency = models.CharField(max_length=3, default="IDR")
    estimate = models.DecimalField(max_digits=14, decimal_places=2)
    actual = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)
    state = models.CharField(max_length=16, choices=State.choices, default=State.RESERVED)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [models.Index(fields=("scope", "period", "state"))]


class BudgetWindow(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    scope = models.CharField(max_length=40)
    period = models.DateField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=("scope", "period"), name="processing_budget_window_unique")]


class WorkerControl(models.Model):
    key = models.CharField(max_length=40, primary_key=True)
    heartbeat_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)


class AdmissionControl(models.Model):
    key = models.CharField(max_length=40, primary_key=True, default="global")
    enabled = models.BooleanField(default=False)
    daily_budget_idr = models.PositiveIntegerField(default=0)
    queue_limit = models.PositiveSmallIntegerField(default=20)
    reason = models.CharField(max_length=500)
    updated_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="admission_changes")
    updated_at = models.DateTimeField(auto_now=True)


class AllowanceReservation(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    allowance = models.OneToOneField(Allowance, on_delete=models.PROTECT, related_name="reservation")
    job = models.OneToOneField(Job, on_delete=models.PROTECT, related_name="allowance_reservation")
    released_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)


class CostEntry(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    attempt = models.OneToOneField(JobAttempt, on_delete=models.PROTECT, related_name="cost")
    original_currency = models.CharField(max_length=3)
    original_amount = models.DecimalField(max_digits=14, decimal_places=6)
    conversion_rate = models.DecimalField(max_digits=18, decimal_places=8)
    conversion_source = models.CharField(max_length=120)
    amount_idr = models.DecimalField(max_digits=14, decimal_places=2)
    reconciled = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)


class IdempotencyRecord(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="idempotency_records")
    operation = models.CharField(max_length=80)
    key = models.CharField(max_length=180)
    request_hash = models.CharField(max_length=64)
    status_code = models.PositiveSmallIntegerField()
    response = models.JSONField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=("owner", "operation", "key"), name="processing_idempotency_owner_operation_key")]
