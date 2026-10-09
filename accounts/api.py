from django.http import JsonResponse
from django.middleware.csrf import get_token
from django.conf import settings

from momenria.http import public_api_view


@public_api_view("GET")
def session(request):
    token = get_token(request)
    # Public launch still requires external evidence in docs/launch-readiness.md.
    return JsonResponse({
        "public_access": settings.PUBLIC_ACCESS,
        "authenticated": request.user.is_authenticated,
        "email": request.user.email if request.user.is_authenticated else None,
        "email_verified": request.user.email_verified if request.user.is_authenticated else False,
        "csrf_token": token,
        "capabilities": {
            "payments_enabled": settings.PAYMENT_PROVIDER != "disabled",
            "corrections_enabled": settings.AI_GATEWAY_MODE == "fake" or settings.AI_GATEWAY_MODE == "9router" and bool(settings.NINE_ROUTER_EDIT_MODEL and settings.NINE_ROUTER_EDIT_PATH),
        },
        "creation_available": True,
        "operating_mode": {"synthetic_processing": settings.AI_GATEWAY_MODE == "fake", "public_launch_ready": False},
        "policy": {"source_retention_days": settings.SOURCE_RETENTION_DAYS, "result_retention_days": settings.RESULT_RETENTION_DAYS, "upload_max_bytes": settings.UPLOAD_MAX_BYTES},
    })
