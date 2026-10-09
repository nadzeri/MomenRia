import base64
import binascii
import hashlib
import io
import json
import uuid
from datetime import timedelta
from http.client import HTTPException
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from PIL import Image, ImageDraw, ImageFont, UnidentifiedImageError
from django.conf import settings
from django.db import transaction
from django.utils import timezone

from operations.models import OutboxEvent
from projects.models import CharacterSheet, MediaAsset, Project, ResultVersion, SourceAsset
from projects.services import detect_faces, emit_analytics
from projects.storage import store_bytes_atomically

from .models import Allowance, BudgetReservation, Job, JobAttempt, WorkerControl
from .services import release_failed_job


class WorkerFailure(Exception):
    def __init__(self, code, uncertain=False):
        super().__init__(code)
        self.code = code
        self.uncertain = uncertain


def claim_job():
    now = timezone.now()
    with transaction.atomic():
        control, _ = WorkerControl.objects.get_or_create(key="global")
        control = WorkerControl.objects.select_for_update().get(key=control.key)
        active = Job.objects.filter(state__in=(Job.State.DISPATCHING, Job.State.PROCESSING, Job.State.FINALIZING), leased_until__gt=now).count()
        if active >= settings.AI_MAX_CONCURRENCY:
            control.heartbeat_at = now
            control.save(update_fields=("heartbeat_at", "updated_at"))
            return None
        job = Job.objects.select_for_update(skip_locked=True).filter(state=Job.State.QUEUED, next_run_at__lte=now).order_by("next_run_at", "created_at").first()
        if not job:
            control.heartbeat_at = now
            control.save(update_fields=("heartbeat_at", "updated_at"))
            return None
        job.state = Job.State.DISPATCHING
        job.lease_token = uuid.uuid4()
        job.fencing_token += 1
        job.leased_until = now + timedelta(minutes=5)
        job.heartbeat_at = now
        job.save(update_fields=("state", "lease_token", "fencing_token", "leased_until", "heartbeat_at", "updated_at"))
        JobAttempt.objects.create(job=job, number=job.attempts.count() + 1)
        control.heartbeat_at = now
        control.save(update_fields=("heartbeat_at", "updated_at"))
        return job


def _assert_inputs_eligible(job):
    try:
        project = Project.objects.get(id=job.project_id, state__in=(Project.State.DRAFT, Project.State.ACTIVE), deletion_epoch=job.deletion_epoch)
    except Project.DoesNotExist as error:
        raise WorkerFailure("project_deleted") from error
    source_ids = [item["source_id"] for item in job.input_snapshot.get("sources", [])]
    eligible = project.sources.filter(id__in=source_ids, status="ready", expires_at__gt=timezone.now(), consent__granted=True).count()
    if eligible != len(source_ids):
        raise WorkerFailure("source_expired")
    for item in job.input_snapshot.get("sources", []):
        if item.get("character_sheet") and not project.character_sheets.filter(id=item["character_sheet"]["id"], source_id=item["source_id"], status="approved", sha256=item["character_sheet"]["sha256"], expires_at__gt=timezone.now()).exists():
            raise WorkerFailure("sheet_not_ready")


def _fake_generation(job):
    if settings.APP_ENV != "test" or settings.AI_GATEWAY_MODE != "fake":
        raise WorkerFailure("gateway_contract_unverified")
    if job.operation == Job.Operation.CHARACTER_SHEET:
        source = SourceAsset.objects.get(id=job.input_snapshot["sources"][0]["source_id"], project_id=job.project_id)
        with source.file.open("rb") as file, Image.open(file) as opened:
            portrait = opened.convert("RGB").resize((768, 512), Image.Resampling.LANCZOS)
        image = Image.new("RGB", (1536, 1024))
        for x, y in ((0, 0), (768, 0), (0, 512), (768, 512)):
            image.paste(portrait, (x, y))
        return image, True, "fake-test", ""
    path = settings.BASE_DIR / "static" / job.project.template.sample_asset
    try:
        with Image.open(path) as source:
            image = source.convert("RGB")
    except (OSError, UnidentifiedImageError) as error:
        raise WorkerFailure("template_asset_invalid") from error
    image = image.resize((2048, 1536), Image.Resampling.LANCZOS)
    return image, True, "fake-test", ""


def _data_url(content, mime_type):
    return f"data:{mime_type};base64,{base64.b64encode(content).decode()}"


def _gateway_images(job):
    if job.operation == Job.Operation.CHARACTER_SHEET:
        images = []
    elif job.operation == Job.Operation.CORRECTION:
        try:
            parent_master = job.parent_result.media.get(kind=MediaAsset.Kind.MASTER, deleted_at__isnull=True)
        except MediaAsset.DoesNotExist as error:
            raise WorkerFailure("parent_master_missing") from error
        with parent_master.file.open("rb") as file:
            parent_bytes = file.read(40 * 1024 * 1024 + 1)
        if len(parent_bytes) > 40 * 1024 * 1024 or hashlib.sha256(parent_bytes).hexdigest() != parent_master.sha256:
            raise WorkerFailure("parent_master_hash_mismatch")
        images = [_data_url(parent_bytes, "image/jpeg")]
    else:
        template = job.project.template
        static_root = (settings.BASE_DIR / "static").resolve()
        template_path = (static_root / template.sample_asset).resolve()
        if not template_path.is_relative_to(static_root) or not template_path.is_file():
            raise WorkerFailure("template_asset_invalid")
        template_bytes = template_path.read_bytes()
        if template.sample_sha256 and hashlib.sha256(template_bytes).hexdigest() != template.sample_sha256:
            raise WorkerFailure("template_hash_mismatch")
        images = [_data_url(template_bytes, "image/png" if template_path.suffix.lower() == ".png" else "image/jpeg")]
    snapshots = job.input_snapshot.get("sources", [])
    sources = SourceAsset.objects.in_bulk(item["source_id"] for item in snapshots)
    references = {}
    for item in snapshots:
        source = sources.get(uuid.UUID(item["source_id"]))
        if not source:
            raise WorkerFailure("source_missing")
        with source.file.open("rb") as file:
            content = file.read(settings.UPLOAD_MAX_BYTES + 1)
        if len(content) > settings.UPLOAD_MAX_BYTES or hashlib.sha256(content).hexdigest() != item["sha256"]:
            raise WorkerFailure("source_hash_mismatch")
        mime_type = "image/png" if source.format.upper() == "PNG" else "image/jpeg"
        images.append(_data_url(content, mime_type))
        references[("primary", item["source_id"])] = images[-1]
        if item.get("character_sheet"):
            reference = item["character_sheet"]
            try:
                sheet = CharacterSheet.objects.get(id=reference["id"], project_id=job.project_id, source_id=item["source_id"], status="approved", expires_at__gt=timezone.now())
                with sheet.file.open("rb") as file:
                    content = file.read(settings.UPLOAD_MAX_BYTES + 1)
            except (CharacterSheet.DoesNotExist, OSError) as error:
                raise WorkerFailure("sheet_missing") from error
            if len(content) > settings.UPLOAD_MAX_BYTES or hashlib.sha256(content).hexdigest() != reference["sha256"]:
                raise WorkerFailure("sheet_hash_mismatch")
            references[("sheet", reference["id"])] = _data_url(content, "image/jpeg")
    if "image_roles" in job.input_snapshot:
        base = images[0]
        images = [base if role["role"] in {"template", "parent"} else references[(role["role"], role.get("source_id") or role.get("sheet_id"))] for role in job.input_snapshot["image_roles"]]
    return images


def _generation_prompt(job):
    if "prompt" in job.input_snapshot:
        return job.input_snapshot["prompt"]
    template = job.project.template
    if job.operation == Job.Operation.CORRECTION:
        return (
            f"Correct only person {job.target_slot.position} in first image using corresponding ordered identity reference. "
            "Preserve every other person, identity, pose, clothing, lighting, framing, background, and image dimensions. "
            "Improve natural facial likeness and detail without adding text, logos, watermarks, people, or objects."
        )
    return (
        f"Create one photorealistic portrait with exactly {template.people_count} people. "
        "Use first image only as composition, setting, wardrobe, lighting, and pose reference. "
        "Use each following image as identity reference for corresponding person, in supplied order. "
        "Preserve distinct identities, natural facial detail, Indonesian appearance, hands, background, and framing. "
        "Do not add or remove people. Do not add text, logos, watermarks, borders, or extra objects."
    )


def _nine_router_generation(job, attempt):
    base_url = settings.NINE_ROUTER_BASE_URL.rstrip("/")
    path = str(job.input_snapshot.get("gateway_path", "")).strip()
    model = str(job.input_snapshot.get("model", "")).strip()
    if not base_url or not path or not model:
        raise WorkerFailure("gateway_not_configured")
    config = job.input_snapshot.get("generation_config", {})
    try:
        images = _gateway_images(job)
    except OSError as error:
        raise WorkerFailure("reference_media_missing") from error
    payload = {
        "model": model,
        "prompt": _generation_prompt(job),
        "n": 1,
        "size": f"{int(config.get('output_width', 2048))}x{int(config.get('output_height', 1536))}",
        "response_format": "b64_json",
        "images": images,
    }
    headers = {"Content-Type": "application/json", "Accept": "application/json", "X-Idempotency-Key": str(attempt.id)}
    if settings.NINE_ROUTER_API_KEY:
        headers["Authorization"] = f"Bearer {settings.NINE_ROUTER_API_KEY}"
    request = Request(f"{base_url}/{path.lstrip('/')}", data=json.dumps(payload, separators=(",", ":")).encode(), headers=headers, method="POST")
    try:
        with urlopen(request, timeout=settings.AI_REQUEST_TIMEOUT_SECONDS) as response:
            content = response.read(40 * 1024 * 1024 + 1)
            request_id = response.headers.get("X-Request-ID", "")
    except HTTPError as error:
        raise WorkerFailure(f"gateway_http_{error.code}", uncertain=error.code >= 500) from error
    except (URLError, OSError, HTTPException) as error:
        raise WorkerFailure("gateway_transport_unknown", uncertain=True) from error
    if len(content) > 40 * 1024 * 1024:
        raise WorkerFailure("gateway_response_too_large", uncertain=True)
    try:
        body = json.loads(content)
        request_id = str(body.get("id") or request_id)[:180]
        if request_id:
            attempt.provider_request_id = request_id
            attempt.save(update_fields=("provider_request_id",))
        encoded = body["data"][0]["b64_json"]
        if not isinstance(encoded, str):
            raise TypeError
        image_bytes = base64.b64decode(encoded, validate=True)
        actual_model = str(body.get("model") or model)[:180]
        image = Image.open(io.BytesIO(image_bytes))
        if image.width * image.height > settings.UPLOAD_MAX_PIXELS:
            raise ValueError
        image.load()
        image = image.convert("RGB")
    except (AttributeError, binascii.Error, json.JSONDecodeError, KeyError, IndexError, TypeError, ValueError, OSError, UnidentifiedImageError) as error:
        raise WorkerFailure("gateway_response_invalid", uncertain=True) from error
    return image, False, actual_model, request_id


def _generate(job, attempt):
    if settings.AI_GATEWAY_MODE == "fake":
        return _fake_generation(job)
    if settings.AI_GATEWAY_MODE == "9router":
        return _nine_router_generation(job, attempt)
    raise WorkerFailure("gateway_contract_unverified")


def _image_bytes(image, quality=94):
    output = io.BytesIO()
    image.save(output, "JPEG", quality=quality, optimize=True)
    return output.getvalue()


def _preview(master):
    image = master.copy()
    image.thumbnail((768, 768), Image.Resampling.LANCZOS)
    draw = ImageDraw.Draw(image, "RGBA")
    text = "MomenRia · PRATINJAU"
    font = ImageFont.load_default(size=24)
    box = draw.textbbox((0, 0), text, font=font)
    x = max(16, image.width - (box[2] - box[0]) - 24)
    y = max(16, image.height - (box[3] - box[1]) - 24)
    draw.rounded_rectangle((x - 10, y - 8, image.width - 14, image.height - 12), radius=8, fill=(20, 50, 38, 175))
    draw.text((x, y), text, font=font, fill=(255, 255, 255, 235))
    return image


def _finish_output(image):
    provider_width, provider_height = image.size
    provider_long_edge = max(image.size)
    if provider_long_edge < settings.AI_UPSCALE_MIN_LONG_EDGE:
        raise WorkerFailure(f"master_too_small_{provider_width}x{provider_height}")
    if provider_long_edge < 2048:
        scale = 2048 / provider_long_edge
        image = image.resize((round(provider_width * scale), round(provider_height * scale)), Image.Resampling.LANCZOS)
    return image, {
        "provider_width": provider_width, "provider_height": provider_height,
        "width": image.width, "height": image.height, "upscaled": provider_long_edge < 2048,
    }


def _finish_character_job(job, attempt, image, synthetic, actual_model):
    if min(image.size) < 768:
        raise WorkerFailure("sheet_too_small")
    content = _image_bytes(image)
    if len(content) > settings.UPLOAD_MAX_BYTES:
        raise WorkerFailure("sheet_too_large")
    with transaction.atomic():
        project = Project.objects.select_for_update().get(id=job.project_id)
        locked = Job.objects.select_for_update().get(id=job.id)
        if locked.lease_token != job.lease_token or locked.fencing_token != job.fencing_token:
            raise WorkerFailure("stale_fencing_token")
        _assert_inputs_eligible(locked)
        if locked.state not in (Job.State.PROCESSING, Job.State.UNCERTAIN):
            raise WorkerFailure("stale_fencing_token")
        sheet = CharacterSheet.objects.select_for_update().get(id=locked.character_sheet_id, project=project)
        if sheet.status != CharacterSheet.Status.PREPARING or sheet.expires_at <= timezone.now():
            raise WorkerFailure("sheet_not_ready")
        store_bytes_atomically(sheet.file, "sheet.jpg", content)
        sheet.sha256 = hashlib.sha256(content).hexdigest()
        sheet.width, sheet.height = image.size
        sheet.synthetic = synthetic
        sheet.status = CharacterSheet.Status.REVIEW
        sheet.save(update_fields=("file", "sha256", "width", "height", "synthetic", "status"))
        locked.state = Job.State.READY
        locked.save(update_fields=("state", "updated_at"))
        locked.budget_reservation.state = BudgetReservation.State.RECONCILED
        locked.budget_reservation.actual = 0 if synthetic else None
        locked.budget_reservation.save(update_fields=("state", "actual"))
        attempt.state = JobAttempt.State.SUCCEEDED
        attempt.actual_model = actual_model
        attempt.finished_at = timezone.now()
        attempt.save(update_fields=("state", "actual_model", "finished_at"))
        project.revision += 1
        project.save(update_fields=("revision", "updated_at"))
        OutboxEvent.objects.create(topic="character_sheet.review", payload={"job_id": str(job.id), "project_id": str(project.id), "character_sheet_id": str(sheet.id)})
        WorkerControl.objects.filter(key="global").update(heartbeat_at=timezone.now())
    return True


def run_job(job):
    with transaction.atomic():
        Project.objects.select_for_update().get(id=job.project_id)
        locked = Job.objects.select_for_update().get(id=job.id)
        if locked.lease_token != job.lease_token or locked.fencing_token != job.fencing_token or locked.state != Job.State.DISPATCHING:
            return False
        attempt = locked.attempts.order_by("-number").first()
        attempt.state = JobAttempt.State.SENT
        attempt.save(update_fields=("state",))
        locked.state = Job.State.PROCESSING
        locked.heartbeat_at = timezone.now()
        locked.save(update_fields=("state", "heartbeat_at", "updated_at"))
    try:
        _assert_inputs_eligible(job)
        master, synthetic, actual_model, provider_request_id = _generate(job, attempt)
        attempt.provider_completed = not synthetic
        attempt.actual_model = actual_model
        attempt.save(update_fields=("provider_completed", "actual_model"))
        if provider_request_id:
            attempt.provider_request_id = provider_request_id
            attempt.save(update_fields=("provider_request_id",))
        if job.operation == Job.Operation.CHARACTER_SHEET:
            return _finish_character_job(job, attempt, master, synthetic, actual_model)
        master, output = _finish_output(master)
        if not synthetic and len(detect_faces(master)) != job.project.template.people_count:
            raise WorkerFailure("output_face_count_mismatch")
        master_bytes = _image_bytes(master)
        preview = _preview(master)
        preview_bytes = _image_bytes(preview, quality=88)
        expires_at = timezone.now() + timedelta(days=settings.RESULT_RETENTION_DAYS)
        with transaction.atomic():
            project = Project.objects.select_for_update().get(id=job.project_id)
            locked = Job.objects.select_for_update().get(id=job.id)
            if locked.lease_token != job.lease_token or locked.fencing_token != job.fencing_token:
                raise WorkerFailure("stale_fencing_token")
            if project.state == Project.State.DELETED or project.deletion_epoch != locked.deletion_epoch:
                raise WorkerFailure("project_deleted")
            _assert_inputs_eligible(locked)
            if locked.state not in (Job.State.PROCESSING, Job.State.UNCERTAIN):
                raise WorkerFailure("stale_fencing_token")
            locked.state = Job.State.FINALIZING
            locked.save(update_fields=("state", "updated_at"))
            number = project.results.count() + 1
            result = ResultVersion.objects.create(
                project=project, parent=locked.parent_result,
                generation_root=locked.parent_result.generation_root if locked.parent_result and locked.parent_result.generation_root else locked.parent_result,
                source_snapshot=locked.input_snapshot["sources"], region_snapshot={"slots": locked.input_snapshot["slots"], "output": output, "generation": {key: locked.input_snapshot[key] for key in ("prompt", "negative_prompt", "image_roles", "model", "gateway_path", "recipe_digest", "capability_version", "generation_config", "template") if key in locked.input_snapshot}},
                configuration_hash=locked.input_snapshot["configuration_hash"], kind=locked.operation,
                number=number, status=ResultVersion.Status.READY, synthetic=synthetic, expires_at=expires_at,
            )
            master_asset = MediaAsset(project=project, result=result, kind=MediaAsset.Kind.MASTER, sha256=hashlib.sha256(master_bytes).hexdigest(), width=master.width, height=master.height, size_bytes=len(master_bytes), expires_at=expires_at)
            store_bytes_atomically(master_asset.file, "master.jpg", master_bytes)
            master_asset.save()
            preview_asset = MediaAsset(project=project, result=result, kind=MediaAsset.Kind.PREVIEW, sha256=hashlib.sha256(preview_bytes).hexdigest(), width=preview.width, height=preview.height, size_bytes=len(preview_bytes), expires_at=expires_at)
            store_bytes_atomically(preview_asset.file, "preview.jpg", preview_bytes)
            preview_asset.save()
            project.selected_result = result
            project.state = Project.State.ACTIVE
            project.revision += 1
            project.save(update_fields=("selected_result", "state", "revision", "updated_at"))
            if locked.allowance_id:
                locked.allowance.consumed_at = timezone.now()
                locked.allowance.save(update_fields=("consumed_at",))
            locked.state = Job.State.READY
            locked.result = result
            locked.save(update_fields=("state", "result", "updated_at"))
            locked.budget_reservation.state = BudgetReservation.State.RECONCILED
            locked.budget_reservation.actual = 0 if synthetic else None
            locked.budget_reservation.save(update_fields=("state", "actual"))
            attempt.state = JobAttempt.State.SUCCEEDED
            attempt.actual_model = actual_model
            attempt.finished_at = timezone.now()
            attempt.save(update_fields=("state", "actual_model", "finished_at"))
            OutboxEvent.objects.create(topic="result.ready", payload={"job_id": str(locked.id), "result_id": str(result.id)})
            emit_analytics("preview_ready" if locked.operation == Job.Operation.CREATION else "correction_completed", owner=locked.owner, project=project, job=locked, result=result)
            WorkerControl.objects.filter(key="global").update(heartbeat_at=timezone.now())
        return True
    except (WorkerFailure, OSError) as error:
        if isinstance(error, OSError):
            error = WorkerFailure("media_io_failure")
        if error.code == "stale_fencing_token":
            return False
        attempt.state = JobAttempt.State.UNCERTAIN if error.uncertain else JobAttempt.State.FAILED
        attempt.error_code = error.code
        attempt.finished_at = timezone.now()
        attempt.save(update_fields=("state", "error_code", "finished_at"))
        if error.uncertain:
            Job.objects.filter(id=job.id, lease_token=job.lease_token, fencing_token=job.fencing_token, state__in=(Job.State.PROCESSING, Job.State.UNCERTAIN)).update(state=Job.State.UNCERTAIN, error_code=error.code)
        else:
            release_failed_job(job, error.code)
        return False
