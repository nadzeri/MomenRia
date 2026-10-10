import uuid

from django.conf import settings
from django.contrib.auth import get_user_model, logout
from django.core.exceptions import ImproperlyConfigured
from django.http import HttpResponseRedirect
from django.urls import reverse
from django.utils import timezone
from django.utils.http import urlencode

from .logging import request_id


class RequestIdMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        value = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        token = request_id.set(value)
        request.request_id = value
        try:
            response = self.get_response(request)
            response["X-Request-ID"] = value
            return response
        finally:
            request_id.reset(token)


class SecurityHeadersMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        qr_origin = (" https://api.midtrans.com" if settings.PAYMENT_ENV == "production" else " https://api.sandbox.midtrans.com") if settings.PAYMENT_PROVIDER == "midtrans" else ""
        response.setdefault("Content-Security-Policy", f"default-src 'self'; img-src 'self' data: blob:{qr_origin}; style-src 'self' 'unsafe-inline'; script-src 'self'; connect-src 'self'; object-src 'none'; base-uri 'self'; frame-ancestors 'none'")
        response.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
        return response


class SessionLifetimeMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.user.is_authenticated:
            now = int(timezone.now().timestamp())
            started = request.session.get("session_started_at")
            if started is None:
                started = now
                request.session["session_started_at"] = now
            if now - started > settings.SESSION_ABSOLUTE_AGE:
                logout(request)
            elif request.user.is_staff:
                last_operator_activity = request.session.get("operator_last_activity", now)
                if now - last_operator_activity > settings.OPERATOR_SESSION_IDLE_SECONDS:
                    logout(request)
                else:
                    request.session["operator_last_activity"] = now
        return self.get_response(request)


class PublicAccessMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        customer_api = request.path.startswith("/api/v1/") and not request.path.startswith("/api/v1/operator/") and request.path != "/api/v1/payments/webhook"
        if settings.PUBLIC_ACCESS and customer_api:
            owner, created = get_user_model().objects.get_or_create(email=settings.PUBLIC_OWNER_EMAIL, defaults={"email_verified": True})
            if owner.is_staff:
                raise ImproperlyConfigured("PUBLIC_OWNER_EMAIL cannot identify staff")
            if created:
                owner.set_unusable_password()
                owner.save(update_fields=("password",))
            elif not owner.email_verified:
                owner.email_verified = True
                owner.save(update_fields=("email_verified", "updated_at"))
            request.user = owner
        return self.get_response(request)


class OperatorMfaMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.path.startswith("/admin") and request.user.is_authenticated and request.user.is_staff:
            from allauth.account.internal.flows.reauthentication import did_recently_authenticate
            from allauth.mfa.models import Authenticator

            enrolled = Authenticator.objects.filter(user=request.user, type__in=(Authenticator.Type.TOTP, Authenticator.Type.WEBAUTHN)).exists()
            if not enrolled:
                return HttpResponseRedirect("/accounts/2fa/")
            if request.method not in {"GET", "HEAD", "OPTIONS"} and not did_recently_authenticate(request):
                return HttpResponseRedirect(f"{reverse('account_reauthenticate')}?{urlencode({'next': request.get_full_path()})}")
        return self.get_response(request)
