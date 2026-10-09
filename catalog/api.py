from django.conf import settings
from pathlib import Path
from django.http import JsonResponse
from django.db.models import Exists, OuterRef

from momenria.http import public_api_view

from .models import Offer, TemplateVersion
from processing.models import AdmissionControl


def template_json(item):
    display_asset = str(Path(item.sample_asset).with_suffix(".webp"))
    return {
        "id": str(item.id), "slug": item.slug, "version": item.version, "name": item.name,
        "occasion": item.occasion, "people_count": item.people_count, "description": item.description,
        "attire": item.attire, "sample_asset": item.sample_asset, "status": item.status,
        "university": item.generation_config.get("university", ""),
        "backdrop": item.generation_config.get("backdrop", ""),
        "character_references": {
            "enabled": item.generation_config.get("prompt_version") == "character-v1",
            "generated_enabled": bool(item.generation_config.get("generated_sheets_enabled")) and (settings.APP_ENV == "test" or bool(item.generation_config.get("capability_verified"))),
        },
        "display_asset": display_asset if (settings.BASE_DIR / "static" / display_asset).is_file() else item.sample_asset,
        "asset_width": item.asset_width, "asset_height": item.asset_height,
        "slots": [{"id": str(slot.id), "position": slot.position, "x": float(slot.x), "y": float(slot.y), "width": float(slot.width), "height": float(slot.height)} for slot in item.slots.all()],
    }


@public_api_view("GET")
def templates(request):
    rows = TemplateVersion.objects.filter(status=TemplateVersion.Status.PUBLISHED, evidence_approved=True).prefetch_related("slots")
    newer = TemplateVersion.objects.filter(slug=OuterRef("slug"), version__gt=OuterRef("version"), status=TemplateVersion.Status.PUBLISHED, evidence_approved=True)
    rows = rows.filter(~Exists(newer))
    offers = Offer.objects.filter(active=True).order_by("price_idr")
    control = AdmissionControl.objects.filter(key="global").first()
    control_enabled = control.enabled if control else settings.APP_ENV == "test"
    budget_enabled = settings.APP_ENV == "test" and settings.ALLOW_UNBOUNDED_TEST_BUDGET or settings.DAILY_BUDGET_IDR > 0 and (not control or control.daily_budget_idr > 0)
    admission_enabled = settings.ADMISSION_ENABLED and control_enabled and budget_enabled and settings.AI_GATEWAY_MODE != "disabled"
    return JsonResponse({"items": [template_json(item) for item in rows], "offers": [{"id": str(offer.id), "name": offer.name, "price_idr": offer.price_idr, "version": offer.version} for offer in offers], "admission_enabled": admission_enabled})
