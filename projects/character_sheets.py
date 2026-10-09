import hashlib
import io

from PIL import Image, ImageDraw, ImageFont, ImageOps, UnidentifiedImageError
from django.conf import settings
from django.db.models import Max
from django.utils import timezone

from momenria.http import ApiError

from .models import CharacterSheet, SourceAsset
from .storage import store_bytes_atomically


SOURCE_RECIPE = "source-layout-v1:1536x1024:24-margin:face-hair-1.7x2.0"


def eligible_sheet(project, source, sheet_id):
    try:
        sheet = project.character_sheets.get(id=sheet_id)
    except (CharacterSheet.DoesNotExist, ValueError) as error:
        raise ApiError(404, "not_found", "Referensi karakter tidak ditemukan.") from error
    if sheet.source_id != source.id:
        raise ApiError(409, "sheet_source_mismatch", "Referensi karakter harus memakai foto asli yang sama.")
    config = project.template.generation_config
    if config.get("identity_strategy") not in {"source_layout", "generated_optional"} or (sheet.mode == CharacterSheet.Mode.GENERATED and (config.get("identity_strategy") != "generated_optional" or not config.get("generated_sheets_enabled"))):
        raise ApiError(409, "sheet_strategy_mismatch", "Referensi ini belum tersedia untuk template yang dipilih. Pakai referensi foto asli, ya.")
    if sheet.status != CharacterSheet.Status.APPROVED or sheet.expires_at <= timezone.now() or not sheet.sha256:
        raise ApiError(409, "sheet_not_ready", "Cek dan setujui kemiripan referensi karakter dulu, ya.")
    if sheet.synthetic and settings.APP_ENV != "test":
        raise ApiError(409, "sheet_not_ready", "Referensi uji tidak bisa dipakai untuk foto ini.")
    return sheet


def sheet_snapshot(sheet):
    return {"id": str(sheet.id), "sha256": sheet.sha256, "version": sheet.version, "mode": sheet.mode, "expires_at": sheet.expires_at.isoformat()}


def sheet_json(sheet):
    available = bool(sheet.sha256) and sheet.status in {CharacterSheet.Status.REVIEW, CharacterSheet.Status.APPROVED, CharacterSheet.Status.REJECTED} and sheet.expires_at > timezone.now()
    return {
        "id": str(sheet.id), "source_id": str(sheet.source_id), "version": sheet.version,
        "mode": sheet.mode, "status": sheet.status, "synthetic": sheet.synthetic,
        "expires_at": sheet.expires_at.isoformat(), "panel_provenance": sheet.panel_provenance,
        "preview_url": f"/api/v1/character-sheets/{sheet.id}/preview" if available else None,
    }


def build_source_sheet(project, source):
    from .services import detect_faces
    from processing.services import _check_storage_headroom

    if source.project_id != project.id or source.status != SourceAsset.Status.READY or source.expires_at <= timezone.now() or not source.consent.granted:
        raise ApiError(409, "source_not_ready", "Foto aslinya tidak tersedia atau izinnya berakhir.")
    recipe_hash = hashlib.sha256(f"{SOURCE_RECIPE}:{source.content_sha256}".encode()).hexdigest()
    existing = project.character_sheets.filter(source=source, recipe_hash=recipe_hash, status=CharacterSheet.Status.APPROVED, expires_at__gt=timezone.now()).first()
    if existing:
        return existing
    _check_storage_headroom()
    try:
        with source.file.open("rb") as file:
            content = file.read(settings.UPLOAD_MAX_BYTES + 1)
        if hashlib.sha256(content).hexdigest() != source.content_sha256 or len(content) > settings.UPLOAD_MAX_BYTES:
            raise ApiError(409, "source_hash_mismatch", "Foto asli berubah. Upload ulang fotonya, ya.")
        with Image.open(io.BytesIO(content)) as opened:
            if opened.width * opened.height > settings.UPLOAD_MAX_PIXELS:
                raise ApiError(422, "too_many_pixels", "Resolusi fotonya terlalu besar.")
            original = opened.convert("RGB")
    except (OSError, UnidentifiedImageError) as error:
        raise ApiError(409, "source_missing", "Foto asli belum bisa dibuka. Upload ulang fotonya, ya.") from error
    faces = detect_faces(original)
    if len(faces) != 1:
        raise ApiError(422, "single_face_required", "Pakai foto dengan satu wajah yang jelas.")
    x, y, width, height = map(float, faces[0][:4])
    bounds = (max(0, int(x - width * .35)), max(0, int(y - height * .65)), min(original.width, int(x + width * 1.35)), min(original.height, int(y + height * 1.35)))
    sheet_image = Image.new("RGB", (1536, 1024), "#f5f3ef")
    draw = ImageDraw.Draw(sheet_image)
    for index, (panel, label) in enumerate(((original, "Original photo"), (original.crop(bounds), "Face and hair detail"))):
        resized = ImageOps.contain(panel, (720, 936), Image.Resampling.LANCZOS)
        sheet_image.paste(resized, (24 + index * 768 + (720 - resized.width) // 2, 24 + (936 - resized.height) // 2))
        draw.text((24 + index * 768, 974), label, font=ImageFont.load_default(size=24), fill="#333333")
    output = io.BytesIO()
    sheet_image.save(output, "JPEG", quality=95, optimize=True)
    content = output.getvalue()
    version = (project.character_sheets.filter(source=source, recipe_hash=recipe_hash).aggregate(value=Max("version"))["value"] or 0) + 1
    sheet = CharacterSheet(
        project=project, source=source, version=version, mode=CharacterSheet.Mode.SOURCE_LAYOUT,
        recipe_hash=recipe_hash, input_snapshot={"source_id": str(source.id), "sha256": source.content_sha256, "recipe": SOURCE_RECIPE},
        sha256=hashlib.sha256(content).hexdigest(), width=1536, height=1024,
        panel_provenance=[{"view": "original", "origin": "source"}, {"view": "face_detail", "origin": "source_crop", "bounds": list(bounds)}],
        status=CharacterSheet.Status.APPROVED, approved_at=timezone.now(), expires_at=source.expires_at,
    )
    try:
        store_bytes_atomically(sheet.file, "sheet.jpg", content)
        sheet.save()
    except Exception:
        sheet.file.delete(save=False)
        raise
    return sheet
