from allauth.account.signals import email_confirmed
from django.contrib.auth.signals import user_logged_in
from django.dispatch import receiver
from django.utils import timezone


@receiver(email_confirmed)
def mark_email_verified(request, email_address, **kwargs):
    user = email_address.user
    if not user.email_verified:
        user.email_verified = True
        user.save(update_fields=("email_verified", "updated_at"))


@receiver(user_logged_in)
def record_authentication(request, user, **kwargs):
    now = int(timezone.now().timestamp())
    request.session["session_started_at"] = now
    request.session["reauthenticated_at"] = now
