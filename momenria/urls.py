import tempfile
from pathlib import Path

from django.conf import settings
from django.contrib import admin
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.http import JsonResponse
from django.urls import include, path
from django.views.generic import TemplateView

from catalog import api as catalog_api
from accounts import api as accounts_api
from commerce import api as commerce_api
from operations import api as operations_api
from processing import api as processing_api
from projects import api as projects_api


def health_live(request):
    return JsonResponse({"status": "ok"})


def health_ready(request):
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
        executor = MigrationExecutor(connection)
        if executor.migration_plan(executor.loader.graph.leaf_nodes()):
            return JsonResponse({"status": "not_ready", "database": "migration_required"}, status=503)
    except Exception:
        return JsonResponse({"status": "not_ready", "database": "unavailable"}, status=503)
    try:
        source_root = Path(settings.MEDIA_ROOT) / "sources"
        source_root.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(dir=source_root):
            pass
        return JsonResponse({"status": "ok", "database": "ok", "private_media": "ok"})
    except Exception:
        return JsonResponse({"status": "not_ready", "database": "ok", "private_media": "not_writable"}, status=503)


urlpatterns = [
    *[
        path(f"{page}/", TemplateView.as_view(template_name=f"public/{page}.html", extra_context={
            "business_name": settings.BUSINESS_NAME,
            "support_email": settings.SUPPORT_EMAIL,
            "support_phone": settings.SUPPORT_PHONE,
            "policy_version": settings.TERMS_VERSION,
            "source_retention_days": settings.SOURCE_RETENTION_DAYS,
            "result_retention_days": settings.RESULT_RETENTION_DAYS,
        }), name=page)
        for page in ("terms", "privacy", "refunds", "contact")
    ],
    path("health/live", health_live),
    path("health/ready", health_ready),
    path("api/v1/templates", catalog_api.templates),
    path("api/v1/session", accounts_api.session),
    path("api/v1/projects", projects_api.projects),
    path("api/v1/projects/<uuid:project_id>", projects_api.project_detail),
    path("api/v1/projects/<uuid:project_id>/sources", projects_api.sources),
    path("api/v1/projects/<uuid:project_id>/character-sheets", projects_api.character_sheets),
    path("api/v1/character-sheets/<uuid:sheet_id>/preview", projects_api.character_sheet_preview),
    path("api/v1/character-sheets/<uuid:sheet_id>/review", projects_api.character_sheet_review),
    path("api/v1/sources/<uuid:source_id>/thumbnail", projects_api.source_thumbnail),
    path("api/v1/projects/<uuid:project_id>/slots/<uuid:slot_id>", projects_api.slot),
    path("api/v1/projects/<uuid:project_id>/undo", projects_api.undo),
    path("api/v1/projects/<uuid:project_id>/jobs", processing_api.jobs),
    path("api/v1/jobs/<uuid:job_id>", processing_api.job_detail),
    path("api/v1/results/<uuid:result_id>/preview", projects_api.preview),
    path("api/v1/results/<uuid:result_id>/master", projects_api.master),
    path("api/v1/results/<uuid:result_id>/greetings", projects_api.greetings),
    path("api/v1/results/<uuid:result_id>/feedback", projects_api.feedback),
    path("api/v1/results/<uuid:result_id>/corrections", processing_api.corrections),
    path("api/v1/results/<uuid:result_id>/orders", commerce_api.orders),
    path("api/v1/orders", commerce_api.order_list),
    path("api/v1/orders/<uuid:order_id>", commerce_api.order_detail),
    path("api/v1/orders/<uuid:order_id>/refresh", commerce_api.order_refresh),
    path("api/v1/orders/<uuid:order_id>/fake-settle", commerce_api.fake_settle),
    path("api/v1/operator/orders/<uuid:order_id>/refunds", commerce_api.refund),
    path("api/v1/payments/webhook", commerce_api.webhook),
    path("api/v1/support/tickets", operations_api.tickets),
    path("api/v1/support/account-access", operations_api.account_access),
    path("api/v1/support/tickets/<uuid:ticket_id>/replies", operations_api.ticket_replies),
    path("api/v1/support/grants/<uuid:grant_id>", operations_api.revoke_grant),
    path("api/v1/analytics", operations_api.analytics),
    path("api/v1/operator/projects/<uuid:project_id>/media/<uuid:media_id>", operations_api.operator_media),
    path("accounts/", include("allauth.urls")),
    path("admin/", admin.site.urls),
    path("", TemplateView.as_view(template_name="app.html", extra_context={"source_retention_days": settings.SOURCE_RETENTION_DAYS, "result_retention_days": settings.RESULT_RETENTION_DAYS, "upload_max_bytes": settings.UPLOAD_MAX_BYTES}), name="app"),
]
