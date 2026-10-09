import uuid

from django.conf import settings
from django.db import models
from django.db.models import Q


class Order(models.Model):
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
    offer = models.ForeignKey("catalog.Offer", on_delete=models.PROTECT, related_name="orders")
    merchant_reference = models.CharField(max_length=80, unique=True)
    provider_transaction_id = models.CharField(max_length=180, null=True, blank=True, unique=True)
    payment_state = models.CharField(max_length=16, choices=PaymentState.choices, default=PaymentState.CREATING)
    fulfillment_state = models.CharField(max_length=24, choices=FulfillmentState.choices, default=FulfillmentState.UNAVAILABLE)
    amount_idr = models.PositiveIntegerField()
    currency = models.CharField(max_length=3, default="IDR")
    result_id_snapshot = models.UUIDField()
    result_sha256 = models.CharField(max_length=64)
    result_width = models.PositiveIntegerField()
    result_height = models.PositiveIntegerField()
    provider_payload = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    expires_at = models.DateTimeField()
    paid_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=("owner", "result_id_snapshot"), condition=Q(payment_state__in=("creating", "pending", "uncertain", "paid")), name="commerce_one_active_order_per_result")]
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
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="entitlements")
    result_id_snapshot = models.UUIDField()
    result = models.ForeignKey("projects.ResultVersion", null=True, blank=True, on_delete=models.SET_NULL, related_name="entitlements")
    order = models.OneToOneField(Order, on_delete=models.PROTECT, related_name="entitlement")
    granted_at = models.DateTimeField(auto_now_add=True)
    revoked_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=("owner", "result_id_snapshot"), condition=Q(revoked_at__isnull=True), name="commerce_active_entitlement_unique")]


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
    requested_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="requested_refunds")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
