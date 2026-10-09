import sys

from django.conf import settings
from django.db import transaction
from django.http import FileResponse, JsonResponse
from django.utils import timezone

from catalog.models import Offer, TemplateVersion
from catalog.api import template_json
from commerce.models import Entitlement
from momenria.http import ApiError, api_view, body_json, uuid_value
from operations.rate_limit import check_rate_limit
from processing.models import Job

from .models import CharacterSheet, MediaAsset, Project, ResultVersion, SourceAsset
from .character_sheets import build_source_sheet, sheet_json
from .services import assign_source, change_template, create_project, delete_project, emit_analytics, get_owned_project, undo_assignment, validate_and_store_source
from .result_services import create_greeting, frame_preview, record_feedback


def latest_feedback(result):
    latest = {}
    for item in sorted(result.feedback.all(), key=lambda row: (row.created_at, str(row.id)), reverse=True):
        latest.setdefault(item.slot_id, {"slot_id": str(item.slot_id) if item.slot_id else None, "accepted": item.accepted, "issue": item.issue, "created_at": item.created_at.isoformat()})
    return list(latest.values())


def project_json(project):
    from processing.api import job_json

    assignments = {str(item.slot_id): str(item.source_id) for item in project.assignments.all()}
    sources = list(project.sources.exclude(status=SourceAsset.Status.DELETED))
    source_by_id = {str(item.id): item for item in sources}

    def references(item):
        values = []
        for reference in item.source_snapshot:
            source = source_by_id.get(str(reference.get("source_id")))
            values.append({"slot_id": str(reference.get("slot_id", "")), "source_id": str(reference.get("source_id", "")), "status": source.status if source else "deleted", "expires_at": source.expires_at.isoformat() if source else reference.get("expires_at"), "thumbnail_url": f"/api/v1/sources/{source.id}/thumbnail" if source and source.status == SourceAsset.Status.READY and source.expires_at > timezone.now() and source.thumbnail else None})
        return values

    def output(item):
        return item.region_snapshot.get("output") if isinstance(item.region_snapshot, dict) else None

    return {
        "id": str(project.id), "template_id": str(project.template_id), "offer_id": str(project.offer_id),
        "created_at": project.created_at.isoformat(), "updated_at": project.updated_at.isoformat(),
        "character_sheets": [sheet_json(sheet) for sheet in project.character_sheets.exclude(status=CharacterSheet.Status.DELETED).order_by("created_at", "version")],
        "template_change_available": not project.results.exists() and not project.jobs.exclude(operation="character_sheet").exists() and not project.jobs.filter(state__in=Job.ACTIVE_STATES).exists(),
        "assigned_sheets": {str(item.slot_id): str(item.character_sheet_id) for item in project.assignments.all() if item.character_sheet_id},
        "template": template_json(project.template),
        "correction_available": True,
        "state": project.state, "revision": project.revision, "selected_result_id": str(project.selected_result_id) if project.selected_result_id else None,
        "assignments": assignments,
        "sources": [{"id": str(item.id), "status": item.status, "validation_code": item.validation_code, "width": item.width, "height": item.height, "expires_at": item.expires_at.isoformat(), "thumbnail_url": f"/api/v1/sources/{item.id}/thumbnail" if item.thumbnail else None} for item in sources],
        "results": [{"id": str(item.id), "number": item.number, "kind": item.kind, "status": item.status, "greeting": item.greeting, "synthetic": item.synthetic, "created_at": item.created_at.isoformat(), "expires_at": item.expires_at.isoformat(), "references": references(item), "output": output(item), "feedback": latest_feedback(item)} for item in project.results.all()],
        "jobs": [job_json(item) for item in project.jobs.order_by("-created_at")[:5]],
    }


@api_view("GET", "POST")
def projects(request):
    if request.method == "GET":
        try:
            offset = int(request.GET.get("offset", "0"))
            limit = min(int(request.GET.get("limit", "50")), 50)
        except ValueError as error:
            raise ApiError(400, "invalid_pagination", "offset dan limit harus berupa bilangan bulat.") from error
        if not 0 <= offset <= sys.maxsize or limit < 1:
            raise ApiError(400, "invalid_pagination", "offset harus berupa bilangan bulat dalam rentang yang didukung dan limit minimal 1.")
        rows = list(Project.objects.filter(owner=request.user).exclude(state=Project.State.DELETED).select_related("template", "offer").prefetch_related("template__slots", "assignments", "sources", "results__feedback", "jobs").order_by("-updated_at", "-id")[offset:offset + limit + 1])
        return JsonResponse({"items": [project_json(project) for project in rows[:limit]], "offset": offset, "limit": limit, "next_offset": offset + limit if len(rows) > limit else None})
    data = body_json(request)
    if set(data) - {"template_id", "offer_id", "assisted", "acquisition_source"} or not isinstance(data.get("assisted", False), bool) or not isinstance(data.get("acquisition_source", ""), str):
        raise ApiError(400, "invalid_fields", "Data proyek tidak valid.")
    try:
        template = TemplateVersion.objects.get(id=uuid_value(data.get("template_id"), "template_id"))
        offer = Offer.objects.get(id=uuid_value(data.get("offer_id"), "offer_id"))
    except (TemplateVersion.DoesNotExist, Offer.DoesNotExist) as error:
        raise ApiError(404, "not_found", "Template atau paketnya nggak ketemu. Coba pilih lagi dari halaman Template.") from error
    project = create_project(request.user, template, offer, assisted=bool(data.get("assisted", False)), acquisition_source=str(data.get("acquisition_source", "")))
    return JsonResponse(project_json(project), status=201)


@api_view("GET", "PATCH", "DELETE")
def project_detail(request, project_id):
    if request.method == "DELETE":
        data = body_json(request)
        valid_fields = ({"confirmation"}, {"confirmation", "password"}) if settings.PUBLIC_ACCESS else ({"confirmation", "password"},)
        if set(data) not in valid_fields or data.get("confirmation") != "DELETE" or (not settings.PUBLIC_ACCESS and not isinstance(data.get("password"), str)):
            raise ApiError(400, "confirmation_required", "Centang konfirmasi dulu kalau kamu mau hapus proyek ini.")
        if not settings.PUBLIC_ACCESS and not request.user.check_password(data["password"]):
            raise ApiError(403, "reauthentication_failed", "Kata sandinya belum cocok. Coba cek dan ketik lagi, ya.")
        project, task = delete_project(request.user, project_id)
        return JsonResponse({"task": "queued", "task_id": str(task.id), "project_id": str(project.id)}, status=202)
    project = get_owned_project(request.user, project_id)
    if request.method == "PATCH":
        data = body_json(request)
        if set(data) == {"selected_result_id", "expected_revision"}:
            if not isinstance(data["expected_revision"], int):
                raise ApiError(400, "invalid_field", "expected_revision harus berupa angka.", {"field": "expected_revision"})
            if project.revision != data["expected_revision"]:
                raise ApiError(409, "stale_revision", "Proyekmu berubah di tab lain. Muat ulang supaya kamu pakai versi terbaru, ya.", {"current_revision": project.revision})
            try:
                result = project.results.get(id=uuid_value(data["selected_result_id"], "selected_result_id"), status=ResultVersion.Status.READY, expires_at__gt=timezone.now())
            except ResultVersion.DoesNotExist as error:
                raise ApiError(404, "not_found", "Versi ini nggak ketemu. Coba pilih versi lain dari proyekmu.") from error
            project.selected_result = result
            project.revision += 1
            project.save(update_fields=("selected_result", "revision", "updated_at"))
        elif set(data) == {"template_id", "expected_revision", "confirmation"}:
            if not isinstance(data["expected_revision"], int) or not isinstance(data["confirmation"], str):
                raise ApiError(400, "invalid_fields", "Data perubahan template tidak valid.")
            try:
                template = TemplateVersion.objects.get(id=uuid_value(data["template_id"], "template_id"))
            except TemplateVersion.DoesNotExist as error:
                raise ApiError(404, "not_found", "Templatenya nggak ketemu. Coba pilih yang lain, ya.") from error
            project = change_template(request.user, project.id, template, data["expected_revision"], data["confirmation"] == "CHANGE_TEMPLATE")
        else:
            raise ApiError(400, "invalid_fields", "Bidang perubahan proyek tidak valid.")
    return JsonResponse(project_json(project))


@api_view("POST", verified=True)
def undo(request, project_id):
    data = body_json(request)
    if set(data) != {"expected_revision"} or not isinstance(data["expected_revision"], int):
        raise ApiError(400, "invalid_fields", "Revisi proyek wajib berupa angka.")
    return JsonResponse(project_json(undo_assignment(request.user, project_id, data["expected_revision"])))


@api_view("POST", verified=True)
def sources(request, project_id):
    check_rate_limit(request, "upload", limit=20, seconds=3600)
    if set(request.POST) != {"upload_key", "consent_version", "consent_granted"} or set(request.FILES) != {"image"} or len(request.FILES.getlist("image")) != 1:
        raise ApiError(400, "invalid_fields", "Data unggahan tidak valid.")
    upload = request.FILES.get("image")
    if not upload:
        raise ApiError(400, "image_required", "Pilih satu foto dulu, ya.")
    try:
        source = validate_and_store_source(
            request.user, project_id, upload, request.POST.get("upload_key", ""),
            request.POST.get("consent_version", ""), request.POST.get("consent_granted") == "true",
        )
    except ApiError as error:
        if error.code in {"face_not_found", "multiple_faces", "face_too_small", "face_blurry", "face_exposure", "face_occluded"}:
            try:
                project = get_owned_project(request.user, project_id)
                emit_analytics("face_detection_failed", owner=request.user, project=project, dimensions={"reason": error.code})
            except ApiError:
                pass
        raise
    return JsonResponse({"id": str(source.id), "status": source.status, "validation_code": source.validation_code, "expires_at": source.expires_at.isoformat()}, status=201)


@api_view("PUT", verified=True)
def slot(request, project_id, slot_id):
    data = body_json(request)
    if not {"source_id", "expected_revision"}.issubset(data) or set(data) - {"source_id", "expected_revision", "move", "character_sheet_id"} or type(data.get("expected_revision")) is not int or ("move" in data and type(data["move"]) is not bool):
        raise ApiError(400, "invalid_fields", "Data penempatan wajah tidak valid.")
    sheet_id = uuid_value(data["character_sheet_id"], "character_sheet_id") if data.get("character_sheet_id") else None
    project = assign_source(request.user, project_id, slot_id, uuid_value(data.get("source_id"), "source_id"), data["expected_revision"], move=bool(data.get("move", False)), character_sheet_id=sheet_id)
    return JsonResponse(project_json(project))


@api_view("POST", verified=True)
def character_sheets(request, project_id):
    check_rate_limit(request, "character-sheet", limit=10, seconds=3600)
    data = body_json(request)
    if set(data) != {"source_id", "mode", "expected_revision"} or data.get("mode") not in CharacterSheet.Mode.values or type(data.get("expected_revision")) is not int:
        raise ApiError(400, "invalid_fields", "Permintaan referensi karakter tidak valid.")
    if data["mode"] == CharacterSheet.Mode.GENERATED:
        from processing.api import job_json
        from processing.services import admit_character_sheet

        sheet, job, created = admit_character_sheet(request.user, project_id, uuid_value(data["source_id"], "source_id"), data["expected_revision"], request.headers.get("Idempotency-Key", ""))
        return JsonResponse({"sheet": sheet_json(sheet), "job": job_json(job)}, status=202 if created else 200)
    with transaction.atomic():
        project = get_owned_project(request.user, project_id, lock=True)
        if project.revision != data["expected_revision"]:
            raise ApiError(409, "stale_revision", "Draf berubah. Muat ulang dulu, ya.")
        try:
            source = project.sources.get(id=uuid_value(data["source_id"], "source_id"), status=SourceAsset.Status.READY, expires_at__gt=timezone.now(), consent__granted=True)
        except SourceAsset.DoesNotExist as error:
            raise ApiError(404, "not_found", "Foto asli tidak ditemukan.") from error
        sheet = build_source_sheet(project, source)
    return JsonResponse({"sheet": sheet_json(sheet)})


@api_view("POST", verified=True)
def character_sheet_review(request, sheet_id):
    from processing.models import Job

    data = body_json(request)
    if set(data) != {"decision", "expected_revision"} or data.get("decision") not in {"approve", "reject"} or type(data.get("expected_revision")) is not int:
        raise ApiError(400, "invalid_fields", "Penilaian referensi karakter tidak valid.")
    try:
        candidate = CharacterSheet.objects.get(id=sheet_id, project__owner=request.user)
    except CharacterSheet.DoesNotExist as error:
        raise ApiError(404, "not_found", "Referensi karakter tidak ditemukan.") from error
    with transaction.atomic():
        project = get_owned_project(request.user, candidate.project_id, lock=True)
        if project.revision != data["expected_revision"]:
            raise ApiError(409, "stale_revision", "Draf berubah. Muat ulang dulu, ya.")
        if project.results.exists() or project.jobs.filter(state__in=Job.ACTIVE_STATES).exists():
            raise ApiError(409, "project_frozen", "Tunggu proses aktif selesai sebelum menilai referensi.")
        sheet = project.character_sheets.select_related("source", "source__consent").get(id=sheet_id)
        if sheet.status != CharacterSheet.Status.REVIEW or sheet.expires_at <= timezone.now() or sheet.source.status != SourceAsset.Status.READY or sheet.source.expires_at <= timezone.now() or not sheet.source.consent.granted:
            raise ApiError(409, "sheet_not_reviewable", "Referensi ini tidak tersedia untuk dinilai.")
        if not project.assignments.filter(source_id=sheet.source_id).exists():
            raise ApiError(409, "source_not_assigned", "Foto asli referensi ini sudah diganti.")
        sheet.status = CharacterSheet.Status.APPROVED if data["decision"] == "approve" else CharacterSheet.Status.REJECTED
        sheet.approved_at = timezone.now() if data["decision"] == "approve" else None
        sheet.save(update_fields=("status", "approved_at"))
        project.revision += 1
        project.save(update_fields=("revision", "updated_at"))
    return JsonResponse({"sheet": sheet_json(sheet), "revision": project.revision})


@api_view("GET")
def character_sheet_preview(request, sheet_id):
    try:
        sheet = CharacterSheet.objects.get(
            id=sheet_id, project__owner=request.user, project__state__in=(Project.State.DRAFT, Project.State.ACTIVE),
            status__in=(CharacterSheet.Status.REVIEW, CharacterSheet.Status.APPROVED, CharacterSheet.Status.REJECTED),
            expires_at__gt=timezone.now(), source__status=SourceAsset.Status.READY, source__expires_at__gt=timezone.now(), source__consent__granted=True,
        )
        response = FileResponse(sheet.file.open("rb"), content_type="image/jpeg")
    except (CharacterSheet.DoesNotExist, FileNotFoundError, ValueError) as error:
        raise ApiError(404, "not_found", "Referensi karakter tidak tersedia.") from error
    response["Cache-Control"] = "private, no-store"
    return response


def _result_for_owner(owner, result_id):
    try:
        return ResultVersion.objects.select_related("project").get(id=result_id, project__owner=owner, project__state__in=(Project.State.DRAFT, Project.State.ACTIVE), status=ResultVersion.Status.READY, expires_at__gt=timezone.now())
    except ResultVersion.DoesNotExist as error:
        raise ApiError(404, "not_found", "Hasilnya nggak ketemu. Coba buka lagi dari Foto saya.") from error


@api_view("GET")
def preview(request, result_id):
    result = _result_for_owner(request.user, result_id)
    format_name = request.GET.get("format", "original")
    formats = {"original": None, "square": (768, 768), "portrait": (576, 768), "story": (432, 768)}
    if format_name not in formats:
        raise ApiError(400, "invalid_format", "Pilih format asli, persegi, potret, atau Story.")
    try:
        media = result.media.get(kind=MediaAsset.Kind.PREVIEW, deleted_at__isnull=True, expires_at__gt=timezone.now())
    except MediaAsset.DoesNotExist as error:
        raise ApiError(404, "not_found", "Preview belum bisa dibuka. Coba lagi dari Foto saya.") from error
    download = request.GET.get("download") == "1"
    try:
        if formats[format_name]:
            with media.file.open("rb") as source:
                content = frame_preview(source, formats[format_name])
        else:
            content = media.file.open("rb")
        suffix = "" if format_name == "original" else f"-{format_name}"
        response = FileResponse(content, content_type="image/jpeg", as_attachment=download, filename=f"momenria-preview-{result.id}{suffix}.jpg")
    except OSError as error:
        raise ApiError(404, "not_found", "Preview belum bisa dibuka. Hubungi Bantuan, ya.") from error
    response["Cache-Control"] = "private, no-store"
    if download:
        emit_analytics("download_completed", owner=request.user, project=result.project, result=result, dimensions={"kind": "preview", "format": format_name})
    return response


@api_view("GET")
def source_thumbnail(request, source_id):
    try:
        source = SourceAsset.objects.select_related("project").get(id=source_id, project__owner=request.user, project__state__in=(Project.State.DRAFT, Project.State.ACTIVE), status=SourceAsset.Status.READY, expires_at__gt=timezone.now())
    except SourceAsset.DoesNotExist as error:
        raise ApiError(404, "not_found", "Foto aslinya nggak ketemu atau masa simpannya sudah habis.") from error
    if not source.thumbnail:
        raise ApiError(404, "not_found", "Preview foto aslinya belum bisa dibuka. Hubungi Bantuan, ya.")
    response = FileResponse(source.thumbnail.open("rb"), content_type="image/jpeg")
    response["Cache-Control"] = "private, no-store"
    return response


@api_view("GET")
def master(request, result_id):
    result = _result_for_owner(request.user, result_id)
    if not Entitlement.objects.filter(owner=request.user, result_id_snapshot=result.id, revoked_at__isnull=True).exists():
        raise ApiError(404, "not_found", "Hasilnya nggak ketemu. Coba buka lagi dari Foto saya.")
    try:
        media = result.media.get(kind=MediaAsset.Kind.MASTER, deleted_at__isnull=True)
    except MediaAsset.DoesNotExist as error:
        raise ApiError(404, "not_found", "Filenya belum bisa dibuka. Hubungi Bantuan, ya.") from error
    response = FileResponse(media.file.open("rb"), content_type="image/jpeg", as_attachment=True, filename=f"momenria-{result.id}.jpg")
    response["Cache-Control"] = "private, no-store"
    emit_analytics("download_completed", owner=request.user, project=result.project, result=result)
    return response


@api_view("POST")
def greetings(request, result_id):
    check_rate_limit(request, "greeting", limit=30, seconds=3600)
    data = body_json(request)
    if set(data) != {"text", "expected_revision"} or not isinstance(data["text"], str) or not isinstance(data["expected_revision"], int):
        raise ApiError(400, "invalid_fields", "Data ucapan tidak valid.")
    result = create_greeting(request.user, result_id, data["text"], data["expected_revision"])
    return JsonResponse({"id": str(result.id), "number": result.number, "kind": result.kind, "expires_at": result.expires_at.isoformat()}, status=201)


@api_view("POST")
def feedback(request, result_id):
    data = body_json(request)
    accepted = data.get("accepted")
    issue = data.get("issue", "")
    if set(data) - {"slot_id", "issue", "accepted"} or not isinstance(issue, str) or issue not in {"", "likeness", "wrong", "missing", "duplicate", "other"} or not (accepted is None or isinstance(accepted, bool)):
        raise ApiError(400, "invalid_fields", "Data penilaian tidak valid.")
    if data.get("slot_id"):
        data["slot_id"] = uuid_value(data["slot_id"], "slot_id")
    item = record_feedback(request.user, result_id, slot_id=data.get("slot_id"), issue=data.get("issue", ""), accepted=data.get("accepted"))
    return JsonResponse({"id": str(item.id)}, status=201)
