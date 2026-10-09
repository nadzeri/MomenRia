import uuid

from django.conf import settings
from django.db import models
from django.db.models import Q


class Order(models.Model):
    class Purpose(models.TextChoices):
        RESULT_DOWNLOAD = "result_download", "Legacy result download"
        GENERATION = "generation", "New picture"

    class PaymentState(models.TextChoices):
        CREATING = "creating", "Creating"
        PENDING = "pending", "Pending"
        UNCERTAIN = "uncertain", "Uncertain"
        PAID = "paid", "Paid"
        FAILED = "failed", "Failed"
        EXPIRED = "expired", "Expired"
        CANCELLED = "cancelled", "Cancelled"

    class FulfillmentState(models.TextChoices):
        UNAVAILABLE = "unavailable", "Unavailable"
        DOWNLOADABLE = "downloadable", "Downloadable"
        DELIVERY_FAILED = "delivery_failed", "Delivery failed"
        ENDED = "ended", "Ended"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="orders")
    project = models.ForeignKey("projects.Project", null=True, blank=True, on_delete=models.SET_NULL, related_name="orders")
    result = models.ForeignKey("projects.ResultVersion", null=True, blank=True, on_delete=models.SET_NULL, related_name="orders")
    job = models.OneToOneField("processing.Job", null=True, blank=True, on_delete=models.PROTECT, related_name="generation_order")
    purpose = models.CharField(max_length=20, choices=Purpose.choices, default=Purpose.RESULT_DOWNLOAD)
    offer = models.ForeignKey("catalog.Offer", on_delete=models.PROTECT, related_name="orders")
    merchant_reference = models.CharField(max_length=80, unique=True)
    provider_transaction_id = models.CharField(max_length=180, null=True, blank=True, unique=True)
    payment_state = models.CharField(max_length=16, choices=PaymentState.choices, default=PaymentState.CREATING)
    fulfillment_state = models.CharField(max_length=24, choices=FulfillmentState.choices, default=FulfillmentState.UNAVAILABLE)
    amount_idr = models.PositiveIntegerField()
    currency = models.CharField(max_length=3, default="IDR")
    result_id_snapshot = models.UUIDField(null=True, blank=True)
    result_sha256 = models.CharField(max_length=64, null=True, blank=True)
    result_width = models.PositiveIntegerField(null=True, blank=True)
    result_height = models.PositiveIntegerField(null=True, blank=True)
    terms_version = models.CharField(max_length=40, null=True, blank=True)
    refund_policy_version = models.CharField(max_length=40, null=True, blank=True)
    policies_accepted_at = models.DateTimeField(null=True, blank=True)
    provider_payload = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    expires_at = models.DateTimeField()
    paid_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=("owner", "result_id_snapshot"), condition=Q(payment_state__in=("creating", "pending", "uncertain")), name="commerce_one_active_order_per_result"),
            models.CheckConstraint(condition=Q(currency="IDR", amount_idr__gt=0), name="commerce_order_positive_idr"),
            models.CheckConstraint(condition=Q(purpose="result_download", job__isnull=True) | Q(purpose="generation", job__isnull=False, policies_accepted_at__isnull=False, terms_version__isnull=False, refund_policy_version__isnull=False), name="commerce_generation_job_and_consent"),
            models.CheckConstraint(condition=~Q(fulfillment_state="downloadable") | Q(result_id_snapshot__isnull=False, result_sha256__isnull=False, result_width__isnull=False, result_height__isnull=False, result_width__gt=0, result_height__gt=0), name="commerce_download_has_result"),
        ]
        indexes = [models.Index(fields=("payment_state", "expires_at")), models.Index(fields=("provider_transaction_id",))]


class PaymentEvent(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    provider = models.CharField(max_length=40)
    provider_event_id = models.CharField(max_length=180)
    order_reference = models.CharField(max_length=80)
    payload_hash = models.CharField(max_length=64)
    verified = models.BooleanField(default=False)
    payload = models.JSONField()
    received_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=("provider", "provider_event_id"), name="commerce_provider_event_unique")]


class Entitlement(models.Model):
    class GrantSource(models.TextChoices):
        TRIAL = "trial", "Trial"
        PAYMENT = "payment", "Payment"
        LEGACY = "legacy", "Historical grant"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="entitlements")
    result_id_snapshot = models.UUIDField()
    result = models.ForeignKey("projects.ResultVersion", null=True, blank=True, on_delete=models.SET_NULL, related_name="entitlements")
    order = models.OneToOneField(Order, null=True, blank=True, on_delete=models.PROTECT, related_name="entitlement")
    grant_source = models.CharField(max_length=16, choices=GrantSource.choices, default=GrantSource.PAYMENT)
    granted_at = models.DateTimeField(auto_now_add=True)
    revoked_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=("owner", "result_id_snapshot"), condition=Q(revoked_at__isnull=True), name="commerce_active_entitlement_unique"),
            models.CheckConstraint(condition=Q(grant_source="payment", order__isnull=False) | Q(grant_source__in=("trial", "legacy"), order__isnull=True), name="commerce_entitlement_source"),
        ]


class Refund(models.Model):
    class State(models.TextChoices):
        REQUESTED = "requested", "Requested"
        PROCESSING = "processing", "Processing"
        SUCCEEDED = "succeeded", "Succeeded"
        FAILED = "failed", "Failed"
        UNCERTAIN = "uncertain", "Uncertain"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    order = models.ForeignKey(Order, on_delete=models.PROTECT, related_name="refunds")
    amount_idr = models.PositiveIntegerField()
    reason = models.CharField(max_length=500)
    idempotency_key = models.CharField(max_length=180, unique=True)
    request_hash = models.CharField(max_length=64, blank=True)
    provider_reference = models.CharField(max_length=180, blank=True, unique=True, null=True)
    state = models.CharField(max_length=16, choices=State.choices, default=State.REQUESTED)
    requested_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT, related_name="requested_refunds")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
