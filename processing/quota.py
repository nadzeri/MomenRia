from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from momenria.http import ApiError
from catalog.models import Offer
from projects.models import ResultVersion

from .models import Allowance, Job


FREE_LIMIT = 3
PRICE_IDR = 9900
TRIAL_POLICY = "three-free-v1"


def initialize_trial_allowances(owner):
    with transaction.atomic():
        get_user_model().objects.select_for_update().get(pk=owner.pk)
        slots = list(Allowance.objects.filter(owner=owner, trial_slot__isnull=False).order_by("trial_slot"))
        if len(slots) == FREE_LIMIT:
            return slots
        history = Job.objects.filter(owner=owner, operation=Job.Operation.CREATION, generation_order__isnull=True).filter(Q(allowance__isnull=True) | Q(allowance__trial_slot__isnull=True))
        if history.filter(state__in=Job.ACTIVE_STATES).exists() or history.filter(state=Job.State.READY, result__isnull=True).exclude(allowance__consumed_at__isnull=False).exists():
            raise ApiError(409, "quota_audit_required", "Riwayat jatah foto perlu diperiksa. Hubungi Bantuan sebelum membuat foto baru.")
        used = ResultVersion.objects.filter(project__owner=owner, kind="creation", synthetic=False, status__in=("ready", "expired", "deleted")).count()
        consumed = Allowance.objects.filter(owner=owner, kind="creation", trial_slot__isnull=True, consumed_at__isnull=False)
        used += consumed.exclude(jobs__result__isnull=False).count()
        consumed_at = timezone.now()
        for number in range(1, FREE_LIMIT + 1):
            Allowance.objects.get_or_create(owner=owner, trial_slot=number, defaults={"kind": Allowance.Kind.CREATION, "policy_version": TRIAL_POLICY, "consumed_at": consumed_at if number <= used else None})
        return list(Allowance.objects.filter(owner=owner, trial_slot__isnull=False).order_by("trial_slot"))


def pricing_for(owner=None):
    provider_ready = settings.PAYMENT_PROVIDER == "fake" and settings.APP_ENV == "test" or settings.PAYMENT_PROVIDER == "midtrans" and bool(settings.PAYMENT_SERVER_KEY) and settings.PAYMENT_QRIS_ACQUIRER in {"gopay", "airpay shopee"} and settings.AI_GATEWAY_MODE != "fake"
    checkout_enabled = settings.PAYMENT_CHECKOUT_ENABLED and provider_ready and Offer.objects.filter(active=True, purchase_unit="generation", price_idr=PRICE_IDR).exists()
    pricing = {"model": "three_free_then_per_picture", "free_limit": FREE_LIMIT, "free_used": None, "free_reserved": None, "free_remaining": None, "price_idr": PRICE_IDR, "currency": "IDR", "checkout_enabled": checkout_enabled, "audit_required": False}
    if owner and owner.is_authenticated:
        try:
            initialize_trial_allowances(owner)
        except ApiError as error:
            if error.code != "quota_audit_required":
                raise
            pricing.update(free_used=0, free_reserved=0, free_remaining=0, checkout_enabled=False, audit_required=True)
            return pricing
        slots = Allowance.objects.filter(owner=owner, trial_slot__isnull=False)
        used = slots.filter(consumed_at__isnull=False).count()
        reserved = slots.filter(consumed_at__isnull=True, reservation__isnull=False, reservation__released_at__isnull=True).count()
        pricing.update(free_used=used, free_reserved=reserved, free_remaining=max(0, FREE_LIMIT - used - reserved))
    return pricing
