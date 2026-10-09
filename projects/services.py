import hashlib
import io
import json
import os
import shutil
import warnings
from datetime import timedelta
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageOps, UnidentifiedImageError
from django.conf import settings
from django.db import IntegrityError, transaction
from django.utils import timezone

from momenria.http import ApiError
from operations.models import AnalyticsEvent, DeletionTask, OutboxEvent, SupportGrant
from processing.models import IdempotencyRecord, Job
from catalog.models import FaceSlot

from .models import AssignmentHistory, Consent, Project, SlotAssignment, SourceAsset
from .storage import store_bytes_atomically
from .character_sheets import build_source_sheet, eligible_sheet


def _detect_faces(image):
    if not settings.FACE_DETECTOR_MODEL.is_file():
        raise ApiError(503, "face_detector_unavailable", "Kami belum bisa cek wajahnya. Coba lagi nanti, ya.")
    pixels = np.asarray(image)
    bgr = cv2.cvtColor(pixels, cv2.COLOR_RGB2BGR)
    height, width = bgr.shape[:2]
    detector = cv2.FaceDetectorYN.create(
        str(settings.FACE_DETECTOR_MODEL), "", (width, height),
        settings.FACE_CONFIDENCE_THRESHOLD, 0.3, 5000,
    )
    _, faces = detector.detect(bgr)
    return bgr, [] if faces is None else faces


def detect_faces(image):
    return _detect_faces(image)[1]


def _validate_single_face(image):
    bgr, faces = _detect_faces(image)
    height, width = bgr.shape[:2]
    count = len(faces)
    if count == 0:
        raise ApiError(422, "face_not_found", "Wajahnya belum terlihat jelas. Coba foto yang lebih dekat dan terang, ya.")
    if count > 1:
        raise ApiError(422, "multiple_faces", "Pilih foto dengan satu wajah saja, ya.")
    face = faces[0]
    x, y, face_width, face_height = face[:4]
    if min(face_width, face_height) < settings.FACE_MIN_SIZE_PX:
        raise ApiError(422, "face_too_small", "Wajahnya terlalu kecil. Pilih foto yang lebih dekat, ya.")
    crop = cv2.cvtColor(bgr[max(0, int(y)):min(height, int(y + face_height)), max(0, int(x)):min(width, int(x + face_width))], cv2.COLOR_BGR2GRAY)
    if not crop.size or cv2.Laplacian(crop, cv2.CV_64F).var() < settings.FACE_BLUR_THRESHOLD:
        raise ApiError(422, "face_blurry", "Wajahnya masih buram. Coba foto yang lebih jelas, ya.")
    brightness = float(crop.mean())
    if brightness < settings.FACE_MIN_BRIGHTNESS or brightness > settings.FACE_MAX_BRIGHTNESS:
        raise ApiError(422, "face_exposure", "Wajahnya terlalu gelap atau terlalu terang. Coba foto dengan cahaya yang lebih merata, ya.")
    landmarks = face[4:14].reshape(5, 2)
    if any(point[0] < x or point[0] > x + face_width or point[1] < y or point[1] > y + face_height for point in landmarks):
        raise ApiError(422, "face_occluded", "Ada bagian wajah yang tertutup. Pilih foto yang wajahnya terlihat lengkap, ya.")


def get_owned_project(owner, project_id, *, lock=False, active=True):
    query = Project.objects.select_related("template", "offer")
    if lock:
        query = query.select_for_update()
    filters = {"id": project_id, "owner": owner}
    if active:
        filters["state__in"] = (Project.State.DRAFT, Project.State.ACTIVE)
    try:
        return query.get(**filters)
    except Project.DoesNotExist as error:
        raise ApiError(404, "not_found", "Proyeknya nggak ketemu. Coba buka lagi dari Foto saya.") from error


def create_project(owner, template, offer, *, assisted=False, acquisition_source=""):
    if template.status != template.Status.PUBLISHED or not template.evidence_approved:
        raise ApiError(409, "template_unavailable", "Template ini belum bisa dipakai. Pilih yang lain dulu, ya.")
    if not offer.active:
        raise ApiError(409, "offer_unavailable", "Paket ini belum tersedia. Coba lagi nanti, ya.")
    project = Project.objects.create(owner=owner, template=template, offer=offer, assisted=assisted, acquisition_source=acquisition_source[:80])
    emit_analytics("template_selected", owner=owner, project=project, dimensions={"template_version": str(template.id), "people_count": template.people_count, "offer": str(offer.id), "assisted": assisted})
    return project


def emit_analytics(event, *, owner=None, project=None, job=None, result=None, order=None, dimensions=None):
    AnalyticsEvent.objects.create(
        event_id=__import__("uuid").uuid4(), event=event, owner=owner,
        project_id=getattr(project, "id", None), job_id=getattr(job, "id", None),
        result_id=getattr(result, "id", None), order_id=getattr(order, "id", None),
        dimensions=dimensions or {},
    )


def validate_and_store_source(owner, project_id, upload, upload_key, consent_version, granted):
    if not upload_key or len(upload_key) > 120:
        raise ApiError(400, "invalid_upload_key", "Upload fotonya belum lengkap. Muat ulang halaman, lalu pilih fotonya lagi.")
    if not granted:
        raise ApiError(400, "consent_required", "Centang izin penggunaan foto dulu, ya.")
    if not consent_version or len(consent_version) > 40:
        raise ApiError(400, "consent_version_required", "Izin fotonya perlu diperbarui. Muat ulang halaman, lalu beri izin lagi, ya.")
    if upload.content_type not in {"image/jpeg", "image/png"}:
        raise ApiError(422, "content_type_mismatch", "Pakai foto JPEG atau PNG, ya.")
    media_root = Path(settings.MEDIA_ROOT)
    media_root.mkdir(parents=True, exist_ok=True)
    usage = shutil.disk_usage(media_root)
    used_percent = ((usage.total - usage.free) * 100) / usage.total
    if usage.free < settings.STORAGE_MIN_FREE_BYTES or used_percent >= settings.STORAGE_MAX_USED_PERCENT:
        raise ApiError(503, "storage_paused", "Penyimpanan kami hampir penuh, jadi upload dijeda dulu. Coba lagi nanti, ya.")
    if not isinstance(upload.size, int) or upload.size > settings.UPLOAD_MAX_BYTES:
        raise ApiError(413, "upload_too_large", "Fotonya lebih dari 10 MB. Pilih foto yang lebih kecil, ya.")
    raw = upload.read(settings.UPLOAD_MAX_BYTES + 1)
    if len(raw) > settings.UPLOAD_MAX_BYTES:
        raise ApiError(413, "upload_too_large", "Fotonya lebih dari 10 MB. Pilih foto yang lebih kecil, ya.")
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", Image.DecompressionBombWarning)
            with Image.open(io.BytesIO(raw)) as opened:
                if opened.width * opened.height > settings.UPLOAD_MAX_PIXELS:
                    raise ApiError(422, "too_many_pixels", "Resolusi fotonya terlalu besar. Kecilkan dulu, lalu upload lagi, ya.")
                if getattr(opened, "is_animated", False):
                    raise ApiError(422, "animated_image", "Pakai foto JPEG atau PNG yang nggak bergerak, ya.")
                if opened.format not in {"JPEG", "PNG"}:
                    raise ApiError(422, "unsupported_format", "Pakai foto JPEG atau PNG, ya.")
                if upload.content_type != {"JPEG": "image/jpeg", "PNG": "image/png"}[opened.format]:
                    raise ApiError(422, "content_type_mismatch", "Format filenya nggak cocok dengan isi foto. Simpan ulang sebagai JPEG atau PNG, lalu coba lagi.")
                opened.verify()
        with Image.open(io.BytesIO(raw)) as opened:
            image = ImageOps.exif_transpose(opened).convert("RGB")
            width, height = image.size
            if width * height > settings.UPLOAD_MAX_PIXELS:
                raise ApiError(422, "too_many_pixels", "Resolusi fotonya terlalu besar. Kecilkan dulu, lalu upload lagi, ya.")
            _validate_single_face(image)
            normalized = io.BytesIO()
            image.save(normalized, "JPEG", quality=92, optimize=True)
            thumbnail_image = image.copy()
            thumbnail_image.thumbnail((512, 512), Image.Resampling.LANCZOS)
            thumbnail = io.BytesIO()
            thumbnail_image.save(thumbnail, "JPEG", quality=88, optimize=True)
    except (Image.DecompressionBombError, Image.DecompressionBombWarning) as error:
        raise ApiError(422, "too_many_pixels", "Resolusi fotonya terlalu besar. Kecilkan dulu, lalu upload lagi, ya.") from error
    except (UnidentifiedImageError, OSError) as error:
        raise ApiError(422, "invalid_image", "Fotonya belum bisa dibaca. Coba file JPEG atau PNG lain, ya.") from error

    with transaction.atomic():
        project = get_owned_project(owner, project_id, lock=True)
        digest = hashlib.sha256(normalized.getvalue()).hexdigest()
        operation = f"source:upload:{project.id}"
        request_hash = hashlib.sha256(json.dumps({"sha256": digest, "consent_version": consent_version}, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
        receipt = IdempotencyRecord.objects.filter(owner=owner, operation=operation, key=upload_key).first()
        if receipt:
            if receipt.request_hash != request_hash:
                raise ApiError(409, "upload_key_conflict", "Upload ini bentrok dengan foto lain. Tutup pemilih foto, lalu pilih ulang fotonya, ya.")
            return SourceAsset.objects.get(id=receipt.response["source_id"], project=project)
        existing = SourceAsset.objects.filter(project=project, upload_key=upload_key).select_related("consent").first()
        if existing:
            if existing.content_sha256 != digest or existing.consent.text_version != consent_version:
                raise ApiError(409, "upload_key_conflict", "Upload ini bentrok dengan foto lain. Tutup pemilih foto, lalu pilih ulang fotonya, ya.")
            IdempotencyRecord.objects.create(owner=owner, operation=operation, key=upload_key, request_hash=request_hash, status_code=201, response={"source_id": str(existing.id)})
            return existing
        duplicate = SourceAsset.objects.filter(project=project, content_sha256=digest, status=SourceAsset.Status.READY, expires_at__gt=timezone.now()).first()
        if duplicate:
            IdempotencyRecord.objects.create(owner=owner, operation=operation, key=upload_key, request_hash=request_hash, status_code=200, response={"source_id": str(duplicate.id)})
            return duplicate
        consent = Consent.objects.create(project=project, owner=owner, text_version=consent_version, granted=True)
        normalized_bytes = normalized.getvalue()
        thumbnail_bytes = thumbnail.getvalue()
        source = SourceAsset(
            project=project, consent=consent, upload_key=upload_key, content_sha256=digest,
            original_name=upload.name[:180], format="JPEG", width=width, height=height,
            size_bytes=len(normalized_bytes), status=SourceAsset.Status.READY,
            thumbnail_sha256=hashlib.sha256(thumbnail_bytes).hexdigest(),
            validation_code="single_face_validated",
            expires_at=timezone.now() + timedelta(days=settings.SOURCE_RETENTION_DAYS),
        )
        try:
            store_bytes_atomically(source.file, "normalized.jpg", normalized_bytes)
            store_bytes_atomically(source.thumbnail, "thumbnail.jpg", thumbnail_bytes)
            source.save()
            IdempotencyRecord.objects.create(owner=owner, operation=operation, key=upload_key, request_hash=request_hash, status_code=201, response={"source_id": str(source.id)})
        except Exception:
            source.file.delete(save=False)
            source.thumbnail.delete(save=False)
            raise
        return source


def assignment_snapshot(project):
    return {str(item.slot_id): {"source_id": str(item.source_id), "character_sheet_id": str(item.character_sheet_id) if item.character_sheet_id else None} for item in project.assignments.all()}


def assign_source(owner, project_id, slot_id, source_id, expected_revision, *, move=False, character_sheet_id=None):
    with transaction.atomic():
        project = get_owned_project(owner, project_id, lock=True)
        if project.revision != expected_revision:
            raise ApiError(409, "stale_revision", "Draf berubah di tab lain. Muat ulang supaya kamu pakai versi terbaru, ya.", {"current_revision": project.revision})
        if project.results.exists() or project.jobs.filter(state__in=Job.ACTIVE_STATES).exists():
            raise ApiError(409, "project_frozen", "Prosesnya sudah mulai, jadi posisi wajah nggak bisa diubah lagi.")
        try:
            slot = project.template.slots.get(id=slot_id)
            source = project.sources.get(id=source_id, status=SourceAsset.Status.READY, expires_at__gt=timezone.now(), consent__granted=True)
        except (FaceSlot.DoesNotExist, SourceAsset.DoesNotExist) as error:
            raise ApiError(404, "not_found", "Wajah atau fotonya nggak ketemu. Buka lagi proyekmu dari Foto saya.") from error
        sheet = eligible_sheet(project, source, character_sheet_id) if character_sheet_id else None
        if not sheet and project.template.generation_config.get("identity_strategy") in {"source_layout", "generated_optional"}:
            sheet = build_source_sheet(project, source)
        prior = assignment_snapshot(project)
        duplicate = project.assignments.filter(source=source).exclude(slot=slot).first()
        if duplicate and not move:
            raise ApiError(409, "source_already_assigned", "Foto ini sudah dipakai di posisi wajah lain. Pilih foto yang berbeda, ya.", {"current_slot_id": str(duplicate.slot_id)})
        AssignmentHistory.objects.create(project=project, revision=project.revision, assignments=prior)
        if duplicate:
            duplicate.delete()
        SlotAssignment.objects.update_or_create(project=project, slot=slot, defaults={"source": source, "character_sheet": sheet, "revision": project.revision + 1})
        project.revision += 1
        project.save(update_fields=("revision", "updated_at"))
        emit_analytics("reference_ready", owner=owner, project=project, dimensions={"slot": str(slot.id)})
        return project


def undo_assignment(owner, project_id, expected_revision):
    with transaction.atomic():
        project = get_owned_project(owner, project_id, lock=True)
        if project.revision != expected_revision:
            raise ApiError(409, "stale_revision", "Draf berubah di tab lain. Muat ulang supaya kamu pakai versi terbaru, ya.", {"current_revision": project.revision})
        if project.results.exists() or project.jobs.filter(state__in=Job.ACTIVE_STATES).exists():
            raise ApiError(409, "project_frozen", "Prosesnya sudah mulai, jadi posisi wajah nggak bisa diubah lagi.")
        history = project.assignment_history.order_by("-revision").first()
        if not history:
            raise ApiError(409, "nothing_to_undo", "Belum ada perubahan posisi wajah yang bisa dibatalkan.")
        valid_sources = {
            str(source.id): source
            for source in project.sources.filter(status=SourceAsset.Status.READY, expires_at__gt=timezone.now(), consent__granted=True)
        }
        valid_slots = {str(slot.id): slot for slot in project.template.slots.all()}
        project.assignments.all().delete()
        for slot_id, reference in history.assignments.items():
            source_id = reference["source_id"] if isinstance(reference, dict) else reference
            if slot_id in valid_slots and source_id in valid_sources:
                sheet_id = reference.get("character_sheet_id") if isinstance(reference, dict) else None
                try:
                    sheet = eligible_sheet(project, valid_sources[source_id], sheet_id) if sheet_id else None
                except ApiError:
                    sheet = None
                SlotAssignment.objects.create(project=project, slot=valid_slots[slot_id], source=valid_sources[source_id], character_sheet=sheet, revision=project.revision + 1)
        history.delete()
        project.revision += 1
        project.save(update_fields=("revision", "updated_at"))
        return project


def change_template(owner, project_id, template, expected_revision, confirmed):
    if not confirmed:
        raise ApiError(400, "confirmation_required", "Konfirmasi dulu kalau kamu mau ganti template, ya.")
    if template.status != template.Status.PUBLISHED or not template.evidence_approved:
        raise ApiError(409, "template_unavailable", "Template ini belum bisa dipakai. Pilih yang lain dulu, ya.")
    with transaction.atomic():
        project = get_owned_project(owner, project_id, lock=True)
        if project.revision != expected_revision:
            raise ApiError(409, "stale_revision", "Draf berubah di tab lain. Muat ulang supaya kamu pakai versi terbaru, ya.", {"current_revision": project.revision})
        if project.results.exists() or project.jobs.exclude(operation=Job.Operation.CHARACTER_SHEET).exists() or project.jobs.filter(state__in=Job.ACTIVE_STATES).exists():
            raise ApiError(409, "project_frozen", "Prosesnya sudah mulai, jadi template nggak bisa diganti lagi.")
        project.assignments.all().delete()
        project.assignment_history.all().delete()
        project.template = template
        project.revision += 1
        project.save(update_fields=("template", "revision", "updated_at"))
        return project


def _write_deletion_tombstone(project_id, deletion_epoch, deleted_at):
    settings.TOMBSTONE_ROOT.mkdir(mode=0o700, parents=True, exist_ok=True)
    path = settings.TOMBSTONE_ROOT / "deletions.jsonl"
    record = json.dumps({"project_id": str(project_id), "deletion_epoch": deletion_epoch, "deleted_at": deleted_at.isoformat()}, separators=(",", ":")) + "\n"
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
    try:
        os.write(descriptor, record.encode())
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def delete_project(owner, project_id):
    from commerce.models import Entitlement, Order

    now = timezone.now()
    with transaction.atomic():
        project = get_owned_project(owner, project_id, lock=True)
        project.state = Project.State.DELETED
        project.deletion_epoch += 1
        project.deleted_at = now
        _write_deletion_tombstone(project.id, project.deletion_epoch, now)
        project.save(update_fields=("state", "deletion_epoch", "deleted_at", "updated_at"))
        safe_jobs = project.jobs.filter(state=Job.State.QUEUED)
        for job in safe_jobs.select_related("budget_reservation"):
            if hasattr(job, "allowance_reservation"):
                job.allowance_reservation.delete()
            job.budget_reservation.state = job.budget_reservation.State.RELEASED
            job.budget_reservation.save(update_fields=("state",))
        project.jobs.filter(state__in=Job.ACTIVE_STATES).update(state=Job.State.CANCELLED, error_code="project_deleted")
        Entitlement.objects.filter(result_id_snapshot__in=project.results.values("id"), revoked_at__isnull=True).update(revoked_at=now)
        Order.objects.filter(project=project, payment_state__in=(Order.PaymentState.CREATING, Order.PaymentState.PENDING, Order.PaymentState.UNCERTAIN)).update(payment_state=Order.PaymentState.CANCELLED, fulfillment_state=Order.FulfillmentState.ENDED)
        Order.objects.filter(project=project, payment_state=Order.PaymentState.PAID).update(fulfillment_state=Order.FulfillmentState.ENDED)
        SupportGrant.objects.filter(project=project, revoked_at__isnull=True).update(revoked_at=now)
        task = DeletionTask.objects.create(project_id_snapshot=project.id, deletion_epoch=project.deletion_epoch, next_run_at=now)
        OutboxEvent.objects.create(topic="project.deleted", payload={"project_id": str(project.id), "deletion_epoch": project.deletion_epoch})
        emit_analytics("deletion_requested", owner=owner, project=project)
        return project, task
