import hashlib
import json
import shutil
from decimal import Decimal, InvalidOperation
from pathlib import Path

from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.db.models import Case, F, Sum, When
from django.db.models.functions import Coalesce
from django.utils import timezone

from momenria.http import ApiError
from operations.models import OutboxEvent
from projects.models import CharacterSheet, Project, ResultVersion, SourceAsset
from projects.services import emit_analytics, get_owned_project
from projects.character_sheets import build_source_sheet, eligible_sheet, sheet_snapshot

from .models import AdmissionControl, Allowance, AllowanceReservation, BudgetReservation, BudgetWindow, CostEntry, IdempotencyRecord, Job
from .quota import initialize_trial_allowances, pricing_for
from .prompts import SHEET_PROMPT, freeze_portrait_prompt, recipe_digest, validate_character_configuration


def canonical_hash(payload):
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def _existing_idempotency(owner, operation, key, request_hash):
    record = IdempotencyRecord.objects.filter(owner=owner, operation=operation, key=key).first()
    if not record:
        return None
    if record.request_hash != request_hash:
        raise ApiError(409, "idempotency_conflict", "Kunci idempotensi sudah dipakai untuk permintaan berbeda.")
    return record


def _check_storage_headroom():
    media_root = Path(settings.MEDIA_ROOT)
    media_root.mkdir(parents=True, exist_ok=True)
    usage = shutil.disk_usage(media_root)
    used_percent = ((usage.total - usage.free) * 100) / usage.total
    if usage.free < settings.STORAGE_MIN_FREE_BYTES or used_percent >= settings.STORAGE_MAX_USED_PERCENT:
        raise ApiError(503, "storage_paused", "Penyimpanan kami hampir penuh, jadi bikin foto baru dijeda dulu. Hasil yang sudah ada tetap bisa dibuka.")


def budget_committed(period):
    return BudgetReservation.objects.filter(period=period).exclude(state=BudgetReservation.State.RELEASED).aggregate(total=Sum(Case(When(state=BudgetReservation.State.RECONCILED, then=Coalesce("actual", "estimate")), default=F("estimate"))))["total"] or Decimal(0)


def reserve_budget(cost_bound):
    try:
        per_attempt_estimate = Decimal(str(cost_bound))
    except InvalidOperation:
        per_attempt_estimate = Decimal(0)
    if not per_attempt_estimate.is_finite() or per_attempt_estimate <= 0:
        raise ApiError(503, "cost_bound_missing", "Kami belum siap memproses foto ini. Hubungi Bantuan, ya.")
    estimate = per_attempt_estimate * Decimal(1 + settings.AI_MAX_SAFE_RETRIES)
    period = timezone.localdate()
    control = AdmissionControl.objects.select_for_update().filter(key="global").first()
    control_enabled = control.enabled if control else settings.APP_ENV == "test"
    unbounded_budget = settings.APP_ENV == "test" and settings.ALLOW_UNBOUNDED_TEST_BUDGET
    budget_limit = None if unbounded_budget else min(settings.DAILY_BUDGET_IDR, control.daily_budget_idr) if control else settings.DAILY_BUDGET_IDR
    queue_limit = min(settings.JOB_QUEUE_LIMIT, control.queue_limit) if control else settings.JOB_QUEUE_LIMIT
    if settings.AI_GATEWAY_MODE == "disabled" or not settings.ADMISSION_ENABLED or not control_enabled or (budget_limit is not None and budget_limit <= 0):
        raise ApiError(503, "admission_paused", "Bikin foto baru lagi dijeda. Hasil yang masih dalam masa simpan tetap bisa didownload.")
    budget_window, _ = BudgetWindow.objects.get_or_create(scope="global", period=period)
    BudgetWindow.objects.select_for_update().get(id=budget_window.id)
    if Job.objects.filter(state__in=(Job.State.QUEUED, Job.State.AWAITING_PAYMENT)).count() >= queue_limit:
        raise ApiError(503, "queue_full", "Antreannya lagi penuh. Coba lagi sebentar, ya.")
    reserved = budget_committed(period)
    if budget_limit is not None and reserved + estimate > budget_limit:
        raise ApiError(503, "budget_exhausted", "Batas pemrosesan hari ini sudah tercapai. Coba lagi besok, ya.")
    return estimate, period


def admit_job(owner, project_id, operation, expected_revision, idempotency_key, *, parent_result_id=None, target_slot_id=None, replacement_source_id=None, correction_action=None, payment_offer=None):
    if not idempotency_key or len(idempotency_key) > 180:
        raise ApiError(400, "idempotency_key_required", "Header Idempotency-Key wajib diisi.")
    payload = {"project_id": str(project_id), "operation": operation, "expected_revision": expected_revision, "parent_result_id": str(parent_result_id or ""), "target_slot_id": str(target_slot_id or ""), "replacement_source_id": str(replacement_source_id or ""), "correction_action": correction_action, "payment_offer_id": str(payment_offer.id) if payment_offer else None}
    request_hash = canonical_hash(payload)
    identity = "job:paid_creation" if payment_offer else f"job:{operation}"
    with transaction.atomic():
        get_user_model().objects.select_for_update().get(pk=owner.pk)
        existing = _existing_idempotency(owner, identity, idempotency_key, request_hash)
        if existing:
            return Job.objects.get(id=existing.response["job_id"]), False
        project = get_owned_project(owner, project_id, lock=True)
        existing = _existing_idempotency(owner, identity, idempotency_key, request_hash)
        if existing:
            return Job.objects.get(id=existing.response["job_id"]), False
        if project.revision != expected_revision:
            raise ApiError(409, "stale_revision", "Proyekmu berubah di tab lain. Muat ulang supaya kamu pakai versi terbaru, ya.", {"current_revision": project.revision})
        if not owner.email_verified:
            raise ApiError(403, "email_not_verified", "Verifikasi emailmu dulu sebelum bikin foto, ya.")
        _check_storage_headroom()
        if project.template.status != project.template.Status.PUBLISHED or not project.template.evidence_approved:
            raise ApiError(409, "variant_unavailable", "Template atau paket ini sudah nggak tersedia. Coba pilih yang lain, ya.")
        if project.jobs.filter(state__in=Job.ACTIVE_STATES).exists():
            active = project.jobs.filter(state__in=Job.ACTIVE_STATES).first()
            raise ApiError(409, "job_active", "Fotonya masih diproses. Cek statusnya di Foto saya tanpa mulai ulang, ya.", {"job_id": str(active.id)})
        if operation not in {Job.Operation.CREATION, Job.Operation.CORRECTION}:
            raise ApiError(400, "invalid_operation", "Operasi tidak didukung.")

        correction_source_snapshot = None
        allowance = None
        if operation == Job.Operation.CREATION:
            assignments = list(project.assignments.select_related("slot", "source", "source__consent", "character_sheet").order_by("slot__position"))
            if len(assignments) != project.template.people_count:
                raise ApiError(409, "project_not_ready", "Tambahkan foto untuk tiap wajah dulu, ya.")
            if any(item.source.status != SourceAsset.Status.READY or item.source.expires_at <= timezone.now() or not item.source.consent.granted for item in assignments):
                raise ApiError(409, "source_not_ready", "Masih ada foto yang belum siap. Cek foto di tiap posisi dulu, ya.")
            initialize_trial_allowances(owner)
            if payment_offer:
                if pricing_for(owner)["free_used"] < 3:
                    raise ApiError(409, "free_pictures_available", "Pakai jatah gratis atau tunggu foto yang masih diproses sebelum membeli foto baru.")
                project.offer = payment_offer
                project.save(update_fields=("offer", "updated_at"))
            else:
                allowance = Allowance.objects.select_for_update(of=("self",)).filter(owner=owner, trial_slot__isnull=False, consumed_at__isnull=True, reservation__isnull=True).order_by("trial_slot").first()
                if not allowance:
                    pricing = pricing_for(owner)
                    if pricing["free_reserved"]:
                        raise ApiError(409, "free_pictures_processing", "Jatah gratis sedang diproses. Tunggu statusnya sebelum membuat foto baru.")
                    from catalog.models import Offer
                    offer = Offer.objects.filter(active=True, purchase_unit="generation", price_idr=9900).first()
                    raise ApiError(402, "payment_required", "Tiga foto gratis sudah terpakai. Foto baru berikutnya Rp9.900.", {"amount_idr": 9900, "currency": "IDR", "offer_id": str(offer.id) if offer else None, "checkout_enabled": pricing["checkout_enabled"]})
            parent_result = None
            target_slot = None
            sources = assignments
        else:
            if correction_action not in {None, "enhance", "replace_reference"}:
                raise ApiError(400, "invalid_correction", "Tindakan koreksi tidak didukung.")
            try:
                parent_result = project.results.get(id=parent_result_id, status=ResultVersion.Status.READY, expires_at__gt=timezone.now())
                target_slot = project.template.slots.get(id=target_slot_id)
            except Exception as error:
                raise ApiError(404, "not_found", "Hasil atau wajah yang mau dikoreksi nggak ketemu. Buka lagi proyekmu dari Foto saya.") from error
            from projects.result_services import authorized_root
            authorized_root(parent_result, owner)
            if correction_action == "replace_reference" and not replacement_source_id:
                raise ApiError(400, "replacement_required", "Pilih foto pengganti dari orang yang sama dulu, ya.")
            correction_source_snapshot = [dict(item) for item in parent_result.source_snapshot]
            if replacement_source_id:
                try:
                    replacement = project.sources.get(id=replacement_source_id, status=SourceAsset.Status.READY, expires_at__gt=timezone.now(), consent__granted=True)
                except SourceAsset.DoesNotExist as error:
                    raise ApiError(404, "not_found", "Foto penggantinya nggak ketemu. Pilih ulang fotonya, ya.") from error
                for item in correction_source_snapshot:
                    if item["slot_id"] == str(target_slot.id):
                        item.update(source_id=str(replacement.id), consent_id=str(replacement.consent_id), sha256=replacement.content_sha256, expires_at=replacement.expires_at.isoformat())
                        item.pop("character_sheet", None)
                        if project.template.generation_config.get("identity_strategy") in {"source_layout", "generated_optional"}:
                            item["character_sheet"] = sheet_snapshot(build_source_sheet(project, replacement))
                        break
            source_ids = {item["source_id"] for item in correction_source_snapshot}
            eligible_sources = project.sources.filter(id__in=source_ids, status=SourceAsset.Status.READY, expires_at__gt=timezone.now(), consent__granted=True).count()
            if eligible_sources != len(source_ids):
                raise ApiError(409, "source_not_ready", "Masih ada foto yang belum siap. Cek foto di tiap posisi dulu, ya.")
            sources = None

        estimate, period = reserve_budget(project.template.generation_config.get("max_cost_idr", 0))

        slots = list(project.template.slots.order_by("position").values("id", "position", "x", "y", "width", "height"))
        source_snapshot = []
        if sources:
            source_snapshot = [{"slot_id": str(item.slot_id), "source_id": str(item.source_id), "consent_id": str(item.source.consent_id), "sha256": item.source.content_sha256, "expires_at": item.source.expires_at.isoformat()} for item in sources]
            for item, assignment in zip(source_snapshot, sources):
                if assignment.character_sheet_id:
                    item["character_sheet"] = sheet_snapshot(eligible_sheet(project, assignment.source, assignment.character_sheet_id))
        else:
            source_snapshot = correction_source_snapshot
            for item in source_snapshot:
                if item.get("character_sheet"):
                    eligible_sheet(project, project.sources.get(id=item["source_id"]), item["character_sheet"]["id"])
        snapshot = {
            "template_id": str(project.template_id), "configuration_hash": project.template.configuration_hash,
            "generation_config": project.template.generation_config, "slots": [{key: str(value) for key, value in row.items()} for row in slots],
            "sources": source_snapshot, "offer_id": str(project.offer_id), "offer_price_idr": project.offer.price_idr,
            "revision": project.revision, "detector": "yunet-2023mar", "model": settings.NINE_ROUTER_GENERATION_MODEL,
            "gateway_path": settings.NINE_ROUTER_GENERATION_PATH, "output": {"master_long_edge_min": 2048, "preview_long_edge": 768},
            "correction_action": correction_action,
        }
        freeze_portrait_prompt(snapshot, project.template, operation, target_slot_id)
        job = Job.objects.create(
            owner=owner, project=project, allowance=allowance, parent_result=parent_result, target_slot=target_slot,
            state=Job.State.AWAITING_PAYMENT if payment_offer else Job.State.QUEUED,
            operation=operation, input_snapshot=snapshot, deletion_epoch=project.deletion_epoch,
            estimated_cost_idr=int(estimate), next_run_at=timezone.now(),
        )
        BudgetReservation.objects.create(job=job, scope="global", period=period, estimate=estimate)
        if allowance:
            AllowanceReservation.objects.create(allowance=allowance, job=job)
        response = {"job_id": str(job.id), "state": job.state, "status_url": f"/api/v1/jobs/{job.id}"}
        IdempotencyRecord.objects.create(owner=owner, operation=identity, key=idempotency_key, request_hash=request_hash, status_code=202, response=response)
        OutboxEvent.objects.create(topic="job.awaiting_payment" if payment_offer else "job.queued", payload=response)
        emit_analytics("creation_requested" if operation == Job.Operation.CREATION else "correction_requested", owner=owner, project=project, job=job)
        return job, True


def admit_character_sheet(owner, project_id, source_id, expected_revision, idempotency_key):
    if not idempotency_key or len(idempotency_key) > 180:
        raise ApiError(400, "idempotency_key_required", "Header Idempotency-Key wajib diisi.")
    operation = "job:character_sheet"
    request_hash = canonical_hash({"project_id": str(project_id), "source_id": str(source_id), "expected_revision": expected_revision})
    with transaction.atomic():
        get_user_model().objects.select_for_update().get(pk=owner.pk)
        project = get_owned_project(owner, project_id, lock=True)
        existing = _existing_idempotency(owner, operation, idempotency_key, request_hash)
        if existing:
            job = project.jobs.select_related("character_sheet").get(id=existing.response["job_id"])
            return job.character_sheet, job, False
        if project.revision != expected_revision:
            raise ApiError(409, "stale_revision", "Draf berubah. Muat ulang dulu, ya.")
        config = project.template.generation_config
        if not owner.email_verified or not config.get("generated_sheets_enabled") or project.template.status != "published" or not project.template.evidence_approved:
            raise ApiError(409, "sheet_generation_unavailable", "Referensi multi-sudut belum tersedia untuk template ini.")
        validate_character_configuration(project.template)
        if project.results.exists():
            raise ApiError(409, "project_frozen", "Referensi karakter disiapkan sebelum foto dibuat.")
        try:
            source = project.sources.get(id=source_id, status=SourceAsset.Status.READY, expires_at__gt=timezone.now(), consent__granted=True)
        except SourceAsset.DoesNotExist as error:
            raise ApiError(404, "not_found", "Foto asli tidak ditemukan.") from error
        if not project.assignments.filter(source=source).exists():
            raise ApiError(409, "source_not_assigned", "Pasang foto asli ke posisi wajah dulu, ya.")
        sheet_config = {"output_width": 1536, "output_height": 1024}
        snapshot = {
            "sources": [{"source_id": str(source.id), "sha256": source.content_sha256, "consent_id": str(source.consent_id), "expires_at": source.expires_at.isoformat()}],
            "model": config.get("model"), "gateway_path": config.get("gateway_path"),
            "prompt": f"Image 1: PERSON_PRIMARY.\n{SHEET_PROMPT}", "generation_config": sheet_config,
            "image_roles": [{"role": "primary", "source_id": str(source.id), "index": 1}],
            "recipe_digest": recipe_digest(), "capability_version": config.get("capability_version", "unverified"),
        }
        if not snapshot["model"] or not snapshot["gateway_path"]:
            raise ApiError(503, "gateway_not_configured", "Rute referensi karakter belum lengkap.")
        recipe_hash = canonical_hash({"sha256": source.content_sha256, "model": snapshot["model"], "gateway_path": snapshot["gateway_path"], "prompt": snapshot["prompt"], "config": sheet_config})
        reusable = project.character_sheets.filter(source=source, recipe_hash=recipe_hash, status__in=(CharacterSheet.Status.PREPARING, CharacterSheet.Status.REVIEW, CharacterSheet.Status.APPROVED), expires_at__gt=timezone.now()).first()
        if reusable:
            job = reusable.preparation_job
        else:
            if project.jobs.filter(state__in=Job.ACTIVE_STATES).exists():
                raise ApiError(409, "job_active", "Proses lain masih berjalan. Tunggu sampai selesai, ya.")
            get_user_model().objects.select_for_update().get(pk=owner.pk)
            previous = CharacterSheet.objects.filter(project__owner=owner, recipe_hash=recipe_hash, mode=CharacterSheet.Mode.GENERATED)
            if previous.count() >= 2:
                raise ApiError(409, "sheet_attempt_limit", "Dua percobaan referensi ini sudah dipakai. Gunakan foto asli atau foto yang lebih jelas.")
            if CharacterSheet.objects.filter(project__owner=owner, mode=CharacterSheet.Mode.GENERATED, created_at__date=timezone.localdate()).count() >= 10:
                raise ApiError(429, "sheet_daily_limit", "Batas referensi karakter hari ini sudah tercapai.")
            _check_storage_headroom()
            estimate, period = reserve_budget(config.get("sheet_max_cost_idr", 0))
            sheet = CharacterSheet.objects.create(
                project=project, source=source, version=previous.count() + 1,
                mode=CharacterSheet.Mode.GENERATED, recipe_hash=recipe_hash, input_snapshot=snapshot,
                panel_provenance=[{"view": view, "origin": "generated_estimate"} for view in ("front", "close_up", "three_quarter", "profile")],
                expires_at=source.expires_at,
            )
            job = Job.objects.create(owner=owner, project=project, character_sheet=sheet, operation=Job.Operation.CHARACTER_SHEET, input_snapshot=snapshot, deletion_epoch=project.deletion_epoch, estimated_cost_idr=int(estimate), next_run_at=timezone.now())
            BudgetReservation.objects.create(job=job, scope="global", period=period, estimate=estimate)
            OutboxEvent.objects.create(topic="job.queued", payload={"job_id": str(job.id), "project_id": str(project.id)})
        IdempotencyRecord.objects.create(owner=owner, operation=operation, key=idempotency_key, request_hash=request_hash, status_code=202, response={"job_id": str(job.id)})
        return job.character_sheet, job, reusable is None


def release_failed_job(job, code):
    with transaction.atomic():
        get_user_model().objects.select_for_update().get(pk=job.owner_id)
        Project.objects.select_for_update().get(pk=job.project_id)
        locked = Job.objects.select_for_update().get(id=job.id)
        if locked.lease_token != job.lease_token or locked.fencing_token != job.fencing_token or locked.state == Job.State.READY:
            return
        job = locked
        if job.state != Job.State.CANCELLED:
            job.state = Job.State.FAILED
        job.error_code = code
        job.save(update_fields=("state", "error_code", "updated_at"))
        if job.character_sheet_id:
            CharacterSheet.objects.filter(pk=job.character_sheet_id, status=CharacterSheet.Status.PREPARING).update(status=CharacterSheet.Status.FAILED)
        if hasattr(job, "allowance_reservation"):
            job.allowance_reservation.delete()
        if hasattr(job, "budget_reservation"):
            costs = CostEntry.objects.filter(attempt__job=job).aggregate(total=Sum("amount_idr"))["total"]
            completed = job.attempts.filter(provider_completed=True).exists()
            job.budget_reservation.state = BudgetReservation.State.RECONCILED if costs is not None or completed else BudgetReservation.State.RELEASED
            job.budget_reservation.actual = costs
            job.budget_reservation.save(update_fields=("state", "actual"))
        from commerce.models import Order
        from commerce.services import resolve_generation_failure
        order = Order.objects.filter(job=job, payment_state=Order.PaymentState.PAID).first()
        if order:
            resolve_generation_failure(order, f"Pembuatan foto dipastikan gagal: {code}")
