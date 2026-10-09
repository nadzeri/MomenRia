from datetime import timedelta

from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.db import transaction
from django.db.models import Q
from django.http import FileResponse, JsonResponse
from django.utils import timezone

from momenria.http import ApiError, api_view, body_json, operator_api_view, public_api_view, uuid_value
from projects.models import MediaAsset, Project
from projects.services import emit_analytics
from projects.services import get_owned_project
from .rate_limit import check_rate_limit

from .models import AccountAccessRequest, AuditEvent, SupportGrant, SupportReply, SupportTicket


def support_text(data, field, minimum, maximum):
    value = data.get(field)
    if not isinstance(value, str) or not minimum <= len(value.strip()) <= maximum:
        raise ApiError(400, "invalid_fields", f"{field} harus berisi {minimum}–{maximum} karakter.", {"field": field})
    return value.strip()


@public_api_view("POST")
def account_access(request):
    check_rate_limit(request, "account_access", limit=5, seconds=3600)
    if request.content_type != "application/json":
        raise ApiError(400, "invalid_fields", "Kirim permintaan sebagai JSON tanpa lampiran foto.")
    data = body_json(request)
    if set(data) != {"email", "subject", "message"}:
        raise ApiError(400, "invalid_fields", "Isi email, topik, dan pesan tanpa lampiran foto.")
    email = support_text(data, "email", 3, 254)
    subject = support_text(data, "subject", 1, 120)
    message = support_text(data, "message", 10, 2000)
    try:
        validate_email(email)
    except ValidationError as error:
        raise ApiError(400, "invalid_email", "Periksa alamat emailmu, ya.", {"field": "email"}) from error
    AccountAccessRequest.objects.create(email=email, subject=subject, message=message)
    return JsonResponse({"received": True, "message": "Permintaan bantuan akses akun sudah dicatat untuk ditinjau pengelola. Ini bukan konfirmasi bahwa akun dengan email tersebut terdaftar."}, status=202)


@api_view("POST")
def ticket_replies(request, ticket_id):
    check_rate_limit(request, "support_reply", limit=20, seconds=3600)
    if request.content_type != "application/json":
        raise ApiError(400, "invalid_fields", "Kirim balasan sebagai JSON tanpa lampiran foto.")
    data = body_json(request)
    if set(data) != {"message"}:
        raise ApiError(400, "invalid_fields", "Kirim pesan balasan tanpa lampiran foto.")
    message = support_text(data, "message", 10, 2000)
    with transaction.atomic():
        ticket = SupportTicket.objects.select_for_update().filter(id=ticket_id, owner=request.user).first()
        if not ticket:
            raise ApiError(404, "not_found", "Tiket bantuan tidak ditemukan.")
        reply = SupportReply.objects.create(ticket=ticket, message=message)
        ticket.status = SupportTicket.Status.WAITING
        ticket.save(update_fields=("status", "updated_at"))
    return JsonResponse({"id": str(reply.id), "status": ticket.status, "message": reply.message, "created_at": reply.created_at.isoformat()}, status=201)


@api_view("GET", "POST")
def tickets(request):
    if request.method == "GET":
        rows = request.user.support_tickets.select_related("project", "order").prefetch_related("messages").order_by("-created_at")[:50]
        grants = request.user.support_grants.filter(revoked_at__isnull=True, expires_at__gt=timezone.now())
        return JsonResponse({"items": [{"id": str(item.id), "subject": item.subject, "message": item.message, "status": item.status, "reply": item.owner_visible_reply, "messages": [{"id": str(reply.id), "message": reply.message, "created_at": reply.created_at.isoformat()} for reply in item.messages.all()], "project_id": str(item.project_id) if item.project_id else None, "order_id": str(item.order_id) if item.order_id else None, "created_at": item.created_at.isoformat(), "updated_at": item.updated_at.isoformat()} for item in rows], "grants": [{"id": str(item.id), "project_id": str(item.project_id), "expires_at": item.expires_at.isoformat()} for item in grants]})
    check_rate_limit(request, "support", limit=10, seconds=3600)
    data = body_json(request)
    message = str(data.get("message", "")).strip()
    subject = str(data.get("subject", "")).strip()
    if set(data) - {"subject", "message", "project_id", "order_id", "image_access"} or not isinstance(data.get("image_access", False), bool) or len(message) < 10 or not subject:
        raise ApiError(400, "invalid_ticket", "Isi topik dan ceritakan kendalamu minimal 10 karakter, ya.")
    project = get_owned_project(request.user, uuid_value(data["project_id"], "project_id")) if data.get("project_id") else None
    order = request.user.orders.filter(id=uuid_value(data["order_id"], "order_id")).first() if data.get("order_id") else None
    if data.get("order_id") and not order:
        raise ApiError(404, "not_found", "Pesanannya nggak ketemu. Coba buka lagi dari halaman Pesanan.")
    ticket = SupportTicket.objects.create(owner=request.user, project=project, order=order, subject=subject[:120], message=message[:2000])
    grant = None
    if data.get("image_access") and project:
        grant = SupportGrant.objects.create(owner=request.user, project=project, purpose=f"Tiket {ticket.id}: {subject}"[:500], expires_at=timezone.now() + timedelta(hours=24))
    return JsonResponse({"id": str(ticket.id), "status": ticket.status, "image_grant_id": str(grant.id) if grant else None}, status=201)


@api_view("DELETE")
def revoke_grant(request, grant_id):
    now = timezone.now()
    updated = SupportGrant.objects.filter(id=grant_id, owner=request.user, revoked_at__isnull=True).update(revoked_at=now)
    if not updated:
        raise ApiError(404, "not_found", "Izin akses fotonya nggak ketemu. Cek lagi di halaman Bantuan, ya.")
    return JsonResponse({"revoked": True})


@operator_api_view("GET")
def operator_media(request, project_id, media_id):
    now = timezone.now()
    with transaction.atomic():
        grant = SupportGrant.objects.select_for_update().filter(Q(staff__isnull=True) | Q(staff=request.user), project_id=project_id, revoked_at__isnull=True, expires_at__gt=now).order_by("expires_at").first()
        if not grant:
            raise ApiError(404, "not_found", "Foto ini belum bisa diakses. Cek izin aksesnya dulu, ya.")
        if grant.staff_id is None:
            grant.staff = request.user
            grant.staff_role = "support"
            grant.save(update_fields=("staff", "staff_role"))
        try:
            media = MediaAsset.objects.get(id=media_id, project_id=project_id, project__state=Project.State.ACTIVE, deleted_at__isnull=True, expires_at__gt=now)
        except MediaAsset.DoesNotExist as error:
            raise ApiError(404, "not_found", "Gambarnya belum bisa dibuka. Coba lagi nanti, ya.") from error
        AuditEvent.objects.create(actor=request.user, action="support_media_viewed", object_type="media_asset", object_id=media.id, reason=grant.purpose, metadata={"grant_id": str(grant.id), "project_id": str(project_id)})
    response = FileResponse(media.file.open("rb"), content_type="image/jpeg")
    response["Cache-Control"] = "private, no-store"
    return response


@api_view("POST")
def analytics(request):
    data = body_json(request)
    if data.get("event") != "face_action_opened" or set(data) - {"event", "project_id", "slot_id"}:
        raise ApiError(400, "invalid_event", "Peristiwa interaksi tidak didukung.")
    project = get_owned_project(request.user, data.get("project_id")) if data.get("project_id") else None
    emit_analytics("face_action_opened", owner=request.user, project=project, dimensions={"slot": str(data.get("slot_id", ""))[:36], "source": "client_untrusted"})
    return JsonResponse({"accepted": True}, status=202)
