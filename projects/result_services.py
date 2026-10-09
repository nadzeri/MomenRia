import hashlib
import io
import unicodedata

from PIL import Image, ImageDraw, ImageFont
from django.conf import settings
from django.db import transaction
from django.utils import timezone

from momenria.http import ApiError
from operations.models import OutboxEvent

from .models import Feedback, MediaAsset, Project, ResultVersion
from .services import emit_analytics, get_owned_project
from .storage import store_bytes_atomically


def _jpeg(image, quality):
    output = io.BytesIO()
    image.save(output, "JPEG", quality=quality, optimize=True)
    return output.getvalue()


def _font(size):
    if settings.RESULT_FONT_PATH:
        return ImageFont.truetype(settings.RESULT_FONT_PATH, size=size)
    if settings.APP_ENV == "test":
        return ImageFont.load_default(size=size)
    raise ApiError(503, "font_unavailable", "Teks ucapan belum bisa dipasang. Hubungi Bantuan, ya.")


def frame_preview(file, canvas_size):
    with Image.open(file) as source:
        image = source.convert("RGB")
    image.thumbnail(canvas_size, Image.Resampling.LANCZOS)
    canvas = Image.new("RGB", canvas_size, "#f5f3ec")
    canvas.paste(image, ((canvas.width - image.width) // 2, (canvas.height - image.height) // 2))
    return io.BytesIO(_jpeg(canvas, 88))


def _validate_greeting(text):
    value = unicodedata.normalize("NFC", str(text).strip())
    if len(value) > 48 or any(unicodedata.category(char).startswith("C") for char in value) or "\n" in value or "\r" in value:
        raise ApiError(422, "invalid_greeting", "Tulis ucapannya dalam satu baris, maksimal 48 karakter, ya.")
    return value


def create_greeting(owner, result_id, text, expected_revision):
    greeting = _validate_greeting(text)
    with transaction.atomic():
        try:
            parent = ResultVersion.objects.select_for_update(of=("self",)).select_related("project", "generation_root").get(
                id=result_id, project__owner=owner, project__state=Project.State.ACTIVE,
                status=ResultVersion.Status.READY, expires_at__gt=timezone.now(),
            )
        except ResultVersion.DoesNotExist as error:
            raise ApiError(404, "not_found", "Hasilnya nggak ketemu. Coba buka lagi dari Foto saya.") from error
        project = get_owned_project(owner, parent.project_id, lock=True)
        if project.revision != expected_revision:
            raise ApiError(409, "stale_revision", "Proyekmu berubah di tab lain. Muat ulang supaya kamu pakai versi terbaru, ya.", {"current_revision": project.revision})
        root = parent.generation_root or parent
        image_version = parent
        while image_version.kind == ResultVersion.Kind.GREETING and image_version.parent_id:
            image_version = image_version.parent
        if project.results.filter(kind=ResultVersion.Kind.GREETING, generation_root=root).count() >= 10:
            raise ApiError(409, "finishing_limit", "Sudah ada 10 versi ucapan. Pilih salah satu versi yang sudah ada, ya.")
        try:
            parent_master = image_version.media.get(kind=MediaAsset.Kind.MASTER, deleted_at__isnull=True)
        except MediaAsset.DoesNotExist as error:
            raise ApiError(409, "master_unavailable", "File hasilnya belum bisa dibuka. Hubungi Bantuan, ya.") from error
        with parent_master.file.open("rb") as source:
            image = Image.open(source).convert("RGB")
            image.load()
        if greeting:
            draw = ImageDraw.Draw(image, "RGBA")
            font = _font(max(24, image.width // 36))
            box = draw.textbbox((0, 0), greeting, font=font)
            text_width = box[2] - box[0]
            if text_width > image.width * 0.82:
                raise ApiError(422, "greeting_too_wide", "Ucapannya kepanjangan untuk foto ini. Coba lebih singkat, ya.")
            x = (image.width - text_width) / 2
            y = image.height * 0.88
            pad = max(12, image.width // 100)
            draw.rounded_rectangle((x - pad, y - pad, x + text_width + pad, y + (box[3] - box[1]) + pad), radius=pad, fill=(18, 35, 28, 155))
            draw.text((x, y), greeting, font=font, fill=(255, 255, 255, 245))
        master_bytes = _jpeg(image, 94)
        preview = image.copy()
        preview.thumbnail((768, 768), Image.Resampling.LANCZOS)
        mark = ImageDraw.Draw(preview, "RGBA")
        mark.text((16, preview.height - 36), "MomenRia · PRATINJAU", font=_font(20), fill=(255, 255, 255, 220), stroke_width=2, stroke_fill=(0, 0, 0, 150))
        preview_bytes = _jpeg(preview, 88)
        result = ResultVersion.objects.create(
            project=project, parent=parent, generation_root=root, source_snapshot=parent.source_snapshot,
            region_snapshot=parent.region_snapshot, configuration_hash=parent.configuration_hash,
            kind=ResultVersion.Kind.GREETING, greeting=greeting, number=project.results.count() + 1,
            status=ResultVersion.Status.READY, synthetic=parent.synthetic, expires_at=root.expires_at,
        )
        for kind, content, width, height in (
            (MediaAsset.Kind.MASTER, master_bytes, image.width, image.height),
            (MediaAsset.Kind.PREVIEW, preview_bytes, preview.width, preview.height),
        ):
            asset = MediaAsset(project=project, result=result, kind=kind, sha256=hashlib.sha256(content).hexdigest(), width=width, height=height, size_bytes=len(content), expires_at=result.expires_at)
            store_bytes_atomically(asset.file, f"{kind}.jpg", content)
            asset.save()
        project.selected_result = result
        project.revision += 1
        project.save(update_fields=("selected_result", "revision", "updated_at"))
        OutboxEvent.objects.create(topic="result.greeting_ready", payload={"result_id": str(result.id), "project_id": str(project.id)})
        return result


def record_feedback(owner, result_id, *, slot_id=None, issue="", accepted=None):
    try:
        result = ResultVersion.objects.select_related("project").get(id=result_id, project__owner=owner)
    except ResultVersion.DoesNotExist as error:
        raise ApiError(404, "not_found", "Hasilnya nggak ketemu. Coba buka lagi dari Foto saya.") from error
    slot = None
    if slot_id:
        try:
            slot = result.project.template.slots.get(id=slot_id)
        except Exception as error:
            raise ApiError(404, "not_found", "Wajahnya nggak ketemu. Coba buka lagi proyekmu.") from error
    feedback = Feedback.objects.create(owner=owner, result=result, slot=slot, issue=str(issue)[:40], accepted=accepted)
    emit_analytics("likeness_feedback", owner=owner, project=result.project, result=result, dimensions={"slot": str(slot.id) if slot else None, "issue": feedback.issue, "accepted": accepted})
    return feedback
