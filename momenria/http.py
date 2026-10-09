import json
import uuid
from functools import wraps

from allauth.mfa.models import Authenticator
from django.core.exceptions import RequestDataTooBig, SuspiciousOperation, TooManyFieldsSent
from django.http import JsonResponse
from django.http.multipartparser import MultiPartParserError


def body_json(request):
    try:
        value = json.loads(request.body or b"{}")
    except (TypeError, ValueError) as error:
        raise ApiError(400, "invalid_json", "Isi permintaan bukan JSON yang valid.") from error
    if not isinstance(value, dict):
        raise ApiError(400, "invalid_json", "Isi permintaan harus berupa objek JSON.")
    return value


def uuid_value(value, field):
    try:
        return uuid.UUID(str(value))
    except (TypeError, ValueError, AttributeError) as error:
        raise ApiError(400, "invalid_field", f"{field} harus berupa UUID yang valid.", {"field": field}) from error


class ApiError(Exception):
    def __init__(self, status, code, message, details=None):
        super().__init__(message)
        self.status = status
        self.code = code
        self.message = message
        self.details = details or {}


def api_view(*methods, verified=False):
    def decorate(fn):
        @wraps(fn)
        def wrapped(request, *args, **kwargs):
            if request.method not in methods:
                return error_response(request, ApiError(405, "method_not_allowed", "Metode tidak didukung."))
            if not request.user.is_authenticated:
                return error_response(request, ApiError(401, "authentication_required", "Masuk dulu untuk lanjut, ya."))
            if verified and not request.user.email_verified:
                return error_response(request, ApiError(403, "email_not_verified", "Verifikasi emailmu dulu sebelum upload foto, ya."))
            try:
                return fn(request, *args, **kwargs)
            except ApiError as error:
                return error_response(request, error)
            except (RequestDataTooBig, TooManyFieldsSent, MultiPartParserError, SuspiciousOperation):
                return error_response(request, ApiError(413, "request_too_large", "Data yang dikirim terlalu besar. Coba kurangi ukuran file atau isi pesannya, ya."))
        return wrapped
    return decorate


def public_api_view(*methods):
    def decorate(fn):
        @wraps(fn)
        def wrapped(request, *args, **kwargs):
            if request.method not in methods:
                return error_response(request, ApiError(405, "method_not_allowed", "Metode tidak didukung."))
            try:
                return fn(request, *args, **kwargs)
            except ApiError as error:
                return error_response(request, error)
            except (RequestDataTooBig, TooManyFieldsSent, MultiPartParserError, SuspiciousOperation):
                return error_response(request, ApiError(413, "request_too_large", "Data yang dikirim terlalu besar. Coba kurangi ukuran file atau isi pesannya, ya."))
        return wrapped
    return decorate


def operator_api_view(*methods, recent_auth=False):
    def decorate(fn):
        @wraps(fn)
        def wrapped(request, *args, **kwargs):
            if request.method not in methods:
                return error_response(request, ApiError(405, "method_not_allowed", "Metode tidak didukung."))
            if not request.user.is_authenticated or not request.user.is_staff:
                return error_response(request, ApiError(404, "not_found", "Sumber daya tidak ditemukan."))
            enrolled = Authenticator.objects.filter(user=request.user, type__in=(Authenticator.Type.TOTP, Authenticator.Type.WEBAUTHN)).exists()
            if not enrolled:
                return error_response(request, ApiError(403, "mfa_required", "Aktifkan autentikasi multifaktor untuk tindakan pengelola."))
            if recent_auth:
                from allauth.account.internal.flows.reauthentication import did_recently_authenticate

                if not did_recently_authenticate(request):
                    return error_response(request, ApiError(403, "reauthentication_required", "Masuk ulang sebelum tindakan sensitif."))
            try:
                return fn(request, *args, **kwargs)
            except ApiError as error:
                return error_response(request, error)
            except (RequestDataTooBig, TooManyFieldsSent, MultiPartParserError, SuspiciousOperation):
                return error_response(request, ApiError(413, "request_too_large", "Data yang dikirim terlalu besar. Coba kurangi ukuran file atau isi pesannya, ya."))
        return wrapped
    return decorate


def error_response(request, error):
    payload = {"code": error.code, "message": error.message, "request_id": getattr(request, "request_id", "-"), "retryable": error.status in {429, 503}}
    payload.update(error.details)
    return JsonResponse(payload, status=error.status)


def csrf_failure(request, reason=""):
    if request.path.startswith("/api/v1/"):
        return error_response(request, ApiError(403, "csrf_failed", "Sesi keamananmu perlu diperbarui. Muat ulang halaman, lalu coba lagi, ya."))
    return JsonResponse({"detail": "CSRF verification failed."}, status=403)
