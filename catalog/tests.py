import hashlib
from importlib import import_module
from types import SimpleNamespace

from django.apps import apps
from io import StringIO

from django.conf import settings
from django.core.management import call_command
from django.db import DatabaseError, connection, transaction
from django.test import TestCase, override_settings
from PIL import Image

from catalog.models import FaceSlot, Offer, TemplateVersion


class CatalogAdmissionTests(TestCase):
    @override_settings(APP_ENV="test", AI_GATEWAY_MODE="fake", ADMISSION_ENABLED=True, DAILY_BUDGET_IDR=0, ALLOW_UNBOUNDED_TEST_BUDGET=True)
    def test_catalog_advertises_explicit_unbounded_test_admission(self):
        response = self.client.get("/api/v1/templates")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["admission_enabled"])

    @override_settings(AI_GATEWAY_MODE="disabled", ADMISSION_ENABLED=True, DAILY_BUDGET_IDR=10000)
    def test_disabled_gateway_is_not_advertised_as_available(self):
        self.assertFalse(self.client.get("/api/v1/templates").json()["admission_enabled"])


@override_settings(APP_ENV="test")
class EventCatalogTests(TestCase):
    def seed(self, publish=False):
        call_command("seed_catalog", test_publish=publish, stdout=StringIO())

    def test_character_versions_preserve_originals_and_catalog_uses_latest_published(self):
        from django.core.management import get_commands

        self.seed(publish=True)
        original = TemplateVersion.objects.get(slug="lebaran")
        original_hash = original.configuration_hash
        self.assertIn("prepare_character_templates", get_commands())
        options = {"model": "provider/pinned", "gateway_path": "/images/generations", "portrait_max_cost_idr": 1500, "sheet_max_cost_idr": 500, "generated_sheets": True, "test_publish": True, "stdout": StringIO()}
        call_command("prepare_character_templates", **options)
        call_command("prepare_character_templates", **options)
        original.refresh_from_db()
        self.assertEqual(original.configuration_hash, original_hash)
        self.assertEqual(TemplateVersion.objects.filter(slug="lebaran").count(), 2)
        new = TemplateVersion.objects.get(slug="lebaran", version=2)
        self.assertEqual(new.generation_config["identity_strategy"], "generated_optional")
        self.assertTrue(new.generation_config["scene"])
        self.assertNotEqual(new.configuration_hash, original.configuration_hash)
        self.assertEqual(list(new.slots.values_list("position", flat=True)), [1, 2])
        items = self.client.get("/api/v1/templates").json()["items"]
        self.assertEqual(len(items), 28)
        self.assertEqual({item["version"] for item in items}, {2})
        self.assertTrue(all(item["character_references"]["generated_enabled"] for item in items))

    def test_event_catalog_assets_slots_and_idempotent_publication(self):
        self.seed(publish=True)
        first = list(FaceSlot.objects.order_by("id").values_list("id", flat=True))
        self.seed(publish=True)
        self.assertEqual(list(FaceSlot.objects.order_by("id").values_list("id", flat=True)), first)
        items = self.client.get("/api/v1/templates").json()["items"]
        self.assertEqual(len(items), 28)
        self.assertEqual(len({item["university"] for item in items if item["university"]}), 8)
        self.assertTrue({"Natal", "Lebaran", "Imlek", "Wisuda", "Pre-wedding", "Bayi", "Ulang Tahun", "Maternity", "Pernikahan"}.issubset({item["occasion"] for item in items}))
        for template in TemplateVersion.objects.prefetch_related("slots"):
            with self.subTest(template=template.slug):
                asset = settings.BASE_DIR / "static" / template.sample_asset
                self.assertEqual(hashlib.sha256(asset.read_bytes()).hexdigest(), template.sample_sha256)
                self.assertTrue(asset.with_suffix(".webp").is_file())
                with Image.open(asset) as image:
                    self.assertEqual(image.size, (template.asset_width, template.asset_height))
                self.assertEqual(template.slots.count(), template.people_count)
                self.assertEqual(list(template.slots.values_list("position", flat=True)), list(range(1, template.people_count + 1)))
                for slot in template.slots.all():
                    self.assertTrue(0 < slot.x < 1 and 0 < slot.y < 1)
        ui = next(item for item in items if item["slug"] == "wisuda-ui")
        self.assertEqual(ui["people_count"], 1)
        self.assertIn("Crystal of Knowledge", ui["backdrop"])

    def test_drafts_stay_private_and_reseeding_preserves_pauses_and_offer(self):
        self.seed()
        self.assertEqual(self.client.get("/api/v1/templates").json()["items"], [])
        self.seed(publish=True)
        template = TemplateVersion.objects.get(slug="wisuda-ui")
        template.status = TemplateVersion.Status.PAUSED
        template.save(update_fields=("status",))
        self.seed()
        self.assertTrue(Offer.objects.get(version=1).active)
        self.seed(publish=True)
        template.refresh_from_db()
        self.assertEqual(template.status, TemplateVersion.Status.PAUSED)
        self.assertNotIn(str(template.pk), {item["id"] for item in self.client.get("/api/v1/templates").json()["items"]})

    def test_copy_migration_updates_stock_descriptions_and_preserves_custom_copy(self):
        self.seed(publish=True)
        migration = import_module("catalog.migrations.0008_friendly_descriptions")
        for slug, old, new in migration.DESCRIPTIONS:
            TemplateVersion.objects.filter(slug=slug, version=1).update(description=old)
        TemplateVersion.objects.filter(slug="home").update(description="Cerita khusus keluarga kami.")
        before = list(TemplateVersion.objects.values_list("id", "status", "configuration_hash"))
        editor = SimpleNamespace(connection=connection)
        migration.update_descriptions(apps, editor)
        migration.update_descriptions(apps, editor)
        descriptions = dict(TemplateVersion.objects.values_list("slug", "description"))
        for slug, old, new in migration.DESCRIPTIONS:
            self.assertEqual(descriptions[slug], "Cerita khusus keluarga kami." if slug == "home" else new)
        self.assertEqual(list(TemplateVersion.objects.values_list("id", "status", "configuration_hash")), before)
        migration.restore_descriptions(apps, editor)
        self.assertEqual(TemplateVersion.objects.get(slug="home").description, "Cerita khusus keluarga kami.")
        self.assertEqual(TemplateVersion.objects.get(slug="studio").description, migration.DESCRIPTIONS[0][1])

    def test_solo_constraint_and_database_guards_survive_migration(self):
        template = TemplateVersion.objects.create(slug="solo", version=1, name="Solo", occasion="Wisuda", people_count=1, description="Solo portrait", sample_asset="app/assets/studio.png", configuration_hash="a" * 64, generation_config={"model": "test"}, evidence_approved=True)
        slot = FaceSlot.objects.create(template=template, position=1, x=.5, y=.3)
        for invalid in (0, 5):
            with self.assertRaises(DatabaseError), transaction.atomic():
                TemplateVersion.objects.filter(pk=template.pk).update(people_count=invalid)
        template.status = TemplateVersion.Status.PUBLISHED
        template.save(update_fields=("status",))
        with self.assertRaises(DatabaseError), transaction.atomic():
            TemplateVersion.objects.filter(pk=template.pk).update(name="Changed")
        with self.assertRaises(DatabaseError), transaction.atomic():
            TemplateVersion.objects.filter(pk=template.pk).update(status="draft")
        with self.assertRaises(DatabaseError), transaction.atomic():
            FaceSlot.objects.filter(pk=slot.pk).update(x=.6)
        with self.assertRaises(DatabaseError), transaction.atomic():
            FaceSlot.objects.filter(pk=slot.pk).delete()
