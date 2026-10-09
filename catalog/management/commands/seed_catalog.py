import hashlib
import json
import uuid
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from PIL import Image

from catalog.models import FaceSlot, Offer, TemplateVersion


BASE_TEMPLATES = (
    ("studio", "Studio Keluarga", "Studio", 4, "Foto bareng yang simpel dan hangat. Cocok dipajang di rumah.", "Linen netral", "app/assets/studio.png", ((.416, .184), (.607, .258), (.397, .471), (.633, .555))),
    ("home", "Momen di Rumah", "Di rumah", 3, "Santai di rumah, dekat sama orang tersayang.", "Kasual senada", "app/assets/home.png", ((.339, .269), (.510, .466), (.671, .326))),
    ("lebaran", "Lebaran Bersama", "Lebaran", 2, "Lebaran makin lengkap dengan foto bareng orang tersayang.", "Busana Lebaran sage", "app/assets/lebaran.png", ((.391, .241), (.646, .308))),
)

EVENT_TEMPLATES = json.loads((Path(__file__).resolve().parents[2] / "event_templates.json").read_text())
TEMPLATES = BASE_TEMPLATES + tuple(
    (item["slug"], item["name"], item["occasion"], item["people"], item["description"], item["attire"],
     f"app/assets/events/{item['slug']}.png", item["faces"])
    for item in EVENT_TEMPLATES
)


class Command(BaseCommand):
    help = "Seed event portrait templates as drafts, or publish synthetic test variants"

    def add_arguments(self, parser):
        parser.add_argument("--test-publish", action="store_true")

    @transaction.atomic
    def handle(self, *args, **options):
        publish = options["test_publish"]
        if publish and settings.APP_ENV != "test":
            raise CommandError("--test-publish is allowed only in APP_ENV=test")
        Offer.objects.get_or_create(version=1, defaults={"name": "Unduhan HD uji", "price_idr": 19900, "active": False})
        Offer.objects.filter(purchase_unit="result_download").update(active=False)
        offer = Offer.objects.get(purchase_unit="generation")
        if publish and not offer.active:
            offer.active = True
            offer.save(update_fields=("active", "activated_at"))
        events = {item["slug"]: item for item in EVENT_TEMPLATES}
        for slug, name, occasion, people, description, attire, asset, faces in TEMPLATES:
            path = settings.BASE_DIR / "static" / asset
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            with Image.open(path) as image:
                asset_width, asset_height = image.size
            config = {"model": "image-generation", "prompt_version": "prototype-v1", "output_width": 2048, "output_height": 1536, "max_cost_idr": 1500}
            if slug in events:
                event = events[slug]
                config.update(prompt_version="events-v1", scene=event["scene"])
                config.update({key: event[key] for key in ("university", "backdrop") if key in event})
            config_hash = hashlib.sha256(repr(sorted(config.items())).encode()).hexdigest()
            template, created = TemplateVersion.objects.get_or_create(
                slug=slug, version=1,
                defaults={"name": name, "occasion": occasion, "people_count": people, "description": description, "attire": attire, "sample_asset": asset, "sample_sha256": digest, "asset_width": asset_width, "asset_height": asset_height, "coordinate_convention": "normalized_top_left", "configuration_hash": config_hash, "generation_config": config, "status": TemplateVersion.Status.DRAFT, "evidence_approved": publish},
            )
            for position, (x, y) in enumerate(faces, 1):
                slot_id = uuid.uuid5(uuid.NAMESPACE_URL, f"momenria:{slug}:v1:slot:{position}")
                FaceSlot.objects.get_or_create(id=slot_id, defaults={"template": template, "position": position, "x": x, "y": y, "width": .12, "height": .16})
            if publish and template.status == TemplateVersion.Status.DRAFT:
                template.evidence_approved = True
                template.status = TemplateVersion.Status.PUBLISHED
                template.save(update_fields=("evidence_approved", "status"))
        self.stdout.write(self.style.SUCCESS(f"Seeded {len(TEMPLATES)} templates and offer {offer.version}; published={publish}"))
