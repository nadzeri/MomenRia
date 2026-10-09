from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from momenria.http import ApiError

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
        history = Job.objects.filter(owner=owner, operation=Job.Operation.CREATION).filter(Q(allowance__isnull=True) | Q(allowance__trial_slot__isnull=True))
        if history.filter(state=Job.State.READY, result__isnull=True, allowance__isnull=True).exists():
            raise ApiError(409, "quota_audit_required", "Riwayat jatah foto perlu diperiksa. Hubungi Bantuan sebelum membuat foto baru.")
        used = history.filter(result__isnull=False, result__synthetic=False).count()
        used = max(used, Allowance.objects.filter(owner=owner, kind=Allowance.Kind.CREATION, trial_slot__isnull=True, consumed_at__isnull=False).count())
        consumed_at = timezone.now()
        for number in range(1, FREE_LIMIT + 1):
            Allowance.objects.get_or_create(owner=owner, trial_slot=number, defaults={"kind": Allowance.Kind.CREATION, "policy_version": TRIAL_POLICY, "consumed_at": consumed_at if number <= used else None})
        return list(Allowance.objects.filter(owner=owner, trial_slot__isnull=False).order_by("trial_slot"))


def pricing_for(owner=None):
    pricing = {"model": "three_free_then_per_picture", "free_limit": FREE_LIMIT, "free_used": None, "free_reserved": None, "free_remaining": None, "price_idr": PRICE_IDR, "currency": "IDR", "checkout_enabled": settings.PAYMENT_CHECKOUT_ENABLED and settings.PAYMENT_PROVIDER != "disabled"}
    if owner and owner.is_authenticated:
        initialize_trial_allowances(owner)
        slots = Allowance.objects.filter(owner=owner, trial_slot__isnull=False)
        used = slots.filter(consumed_at__isnull=False).count()
        reserved = slots.filter(consumed_at__isnull=True, reservation__released_at__isnull=True, reservation__job__state__in=Job.ACTIVE_STATES).count()
        pricing.update(free_used=used, free_reserved=reserved, free_remaining=max(0, FREE_LIMIT - used - reserved))
    return pricing
