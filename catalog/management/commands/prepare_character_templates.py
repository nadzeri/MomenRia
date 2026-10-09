import hashlib
import json
import uuid

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from catalog.models import FaceSlot, TemplateVersion
from processing.prompts import PROMPT_VERSION, recipe_digest


SCENES = {
    "studio": "A natural family studio portrait against a warm neutral backdrop, with soft even lighting and the exact grouping shown in the template.",
    "home": "A family relaxing together in a cozy living room, with warm natural window light and the exact seating and grouping shown in the template.",
    "lebaran": "A couple celebrating Lebaran in coordinated sage clothing, with festive home decor, soft natural light and the pose shown in the template.",
}


class Command(BaseCommand):
    help = "Create new character-reference template versions as drafts without changing existing versions"

    def add_arguments(self, parser):
        parser.add_argument("--model", default=settings.NINE_ROUTER_GENERATION_MODEL)
        parser.add_argument("--gateway-path", default=settings.NINE_ROUTER_GENERATION_PATH)
        parser.add_argument("--portrait-max-cost-idr", type=int, required=True)
        parser.add_argument("--sheet-max-cost-idr", type=int, default=0)
        parser.add_argument("--reference-max-images", type=int, default=9)
        parser.add_argument("--generated-sheets", action="store_true")
        parser.add_argument("--benchmark-arm", choices=list("ABCDE"))
        parser.add_argument("--slug", help="Limit preparation to one existing template slug")
        parser.add_argument("--test-publish", action="store_true")

    @transaction.atomic
    def handle(self, *args, **options):
        if options["test_publish"] and settings.APP_ENV != "test":
            raise CommandError("--test-publish is allowed only in APP_ENV=test")
        if not options["model"] or not options["gateway_path"]:
            raise CommandError("A pinned model and gateway path are required")
        if options["portrait_max_cost_idr"] <= 0 or options["reference_max_images"] < 1 or options["generated_sheets"] and options["sheet_max_cost_idr"] <= 0:
            raise CommandError("Positive cost bounds and an image limit are required")
        seen, created = set(), 0
        for original in list(TemplateVersion.objects.order_by("slug", "-version")):
            if options["slug"] and original.slug != options["slug"]:
                continue
            if original.slug in seen:
                continue
            seen.add(original.slug)
            config = dict(original.generation_config)
            config.update(
                prompt_version=PROMPT_VERSION, recipe_digest=recipe_digest(),
                identity_strategy="generated_optional" if options["generated_sheets"] else "source_layout",
                scene=config.get("scene") or SCENES.get(original.slug, original.description),
                wardrobe_policy=f"{original.attire}. Preserve the original person's head covering and identity-specific details.",
                model=options["model"], gateway_path=options["gateway_path"],
                max_cost_idr=options["portrait_max_cost_idr"], sheet_max_cost_idr=options["sheet_max_cost_idr"],
                reference_max_images=options["reference_max_images"], reference_order="template_first",
                generated_sheets_enabled=options["generated_sheets"], negative_constraints_enabled=True,
                capability_version="unverified", capability_verified=False,
                output_width=2048, output_height=1536,
            )
            arm = options["benchmark_arm"]
            if arm:
                config.update(benchmark_arm=arm, identity_strategy={"A": "originals", "B": "originals", "C": "originals", "D": "source_layout", "E": "generated_optional"}[arm], negative_constraints_enabled=arm not in "AB", generated_sheets_enabled=arm == "E")
                if arm == "A":
                    config.pop("prompt_version")
                if arm == "E" and options["sheet_max_cost_idr"] <= 0:
                    raise CommandError("Arm E requires a positive sheet cost bound")
            if settings.NINE_ROUTER_EDIT_MODEL and settings.NINE_ROUTER_EDIT_PATH:
                config.update(edit_model=settings.NINE_ROUTER_EDIT_MODEL, edit_path=settings.NINE_ROUTER_EDIT_PATH)
            digest = hashlib.sha256(json.dumps(config, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
            if original.configuration_hash == digest:
                continue
            fields = {name: getattr(original, name) for name in ("slug", "name", "occasion", "people_count", "description", "attire", "sample_asset", "sample_sha256", "asset_width", "asset_height")}
            template = TemplateVersion.objects.create(**fields, version=original.version + 1, coordinate_convention="normalized_center", generation_config=config, configuration_hash=digest)
            for slot in original.slots.all():
                FaceSlot.objects.create(id=uuid.uuid5(template.id, str(slot.position)), template=template, position=slot.position, x=slot.x, y=slot.y, width=slot.width, height=slot.height)
            if options["test_publish"]:
                template.evidence_approved = True
                template.status = TemplateVersion.Status.PUBLISHED
                template.save(update_fields=("evidence_approved", "status"))
            created += 1
        self.stdout.write(f"Created {created} character-reference versions; existing templates unchanged. Gateway capability and likeness evidence still required.")
