import hashlib
import io
import tempfile
from datetime import timedelta

from PIL import Image
from django.core.files.base import ContentFile
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase, override_settings
from django.utils import timezone

from accounts.models import User
from catalog.models import Offer, TemplateVersion
from commerce.models import Entitlement
from projects.models import MediaAsset, Project, ResultVersion
from projects.result_services import export_dimensions
from .models import Allowance, Job
from .quota import initialize_trial_allowances, pricing_for


class HistoricalPricingTests(TestCase):
    def setUp(self):
        self.media = tempfile.TemporaryDirectory()
        self.addCleanup(self.media.cleanup)
        self.settings = override_settings(MEDIA_ROOT=self.media.name)
        self.settings.enable()
        self.addCleanup(self.settings.disable)
        self.owner = User.objects.create_user("history@example.com", "test-password", email_verified=True)
        self.operator = User.objects.create_superuser("audit@example.com", "test-password")
        offer = Offer.objects.get(purchase_unit="generation")
        template = TemplateVersion.objects.create(slug="history", version=1, name="History", occasion="Lebaran", people_count=1, description="History", sample_asset="app/assets/lebaran.png", configuration_hash="a" * 64, generation_config={"model": "fake"})
        self.project = Project.objects.create(owner=self.owner, template=template, offer=offer, state="active")

    def result(self, **changes):
        values = dict(project=self.project, kind="creation", number=self.project.results.count() + 1, source_snapshot={}, region_snapshot={}, configuration_hash="a" * 64, status="ready", expires_at=timezone.now() + timedelta(days=2))
        values.update(changes)
        return ResultVersion.objects.create(**values)

    def asset(self, result, kind, color):
        image = Image.new("RGB", (2048, 1536), color)
        data = io.BytesIO()
        image.save(data, "JPEG", quality=94)
        content = data.getvalue()
        asset = MediaAsset(project=self.project, result=result, kind=kind, sha256=hashlib.sha256(content).hexdigest(), width=image.width, height=image.height, size_bytes=len(content), expires_at=result.expires_at)
        asset.file.save(f"{kind}.jpg", ContentFile(content), save=True)
        return asset

    def test_history_counts_deleted_expired_roots_and_orphan_consumption(self):
        self.result(status="deleted")
        self.result(status="expired", expires_at=timezone.now() - timedelta(days=1))
        self.result(synthetic=True)
        self.result(kind="correction")
        Allowance.objects.create(owner=self.owner, kind="creation", policy_version="old", consumed_at=timezone.now())
        self.assertEqual(pricing_for(self.owner)["free_used"], 3)

    def test_incomplete_or_active_history_blocks_creation_without_breaking_session(self):
        job = Job.objects.create(owner=self.owner, project=self.project, operation="creation", state="ready", input_snapshot={}, deletion_epoch=0, estimated_cost_idr=0, next_run_at=timezone.now())
        self.client.force_login(self.owner)
        response = self.client.get("/api/v1/session")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["pricing"]["audit_required"])
        self.assertFalse(response.json()["creation_available"])
        self.assertFalse(Allowance.objects.filter(owner=self.owner).exists())
        job.state = "uncertain"
        job.save()
        with self.assertRaises(Exception) as error:
            initialize_trial_allowances(self.owner)
        self.assertEqual(error.exception.code, "quota_audit_required")

    def test_history_command_dry_run_and_repeat_preserve_master_and_revocations(self):
        root = self.result()
        master = self.asset(root, "master", (96, 96, 96))
        self.asset(root, "preview", "red")
        revoked = self.result()
        self.asset(revoked, "master", "blue")
        Entitlement.objects.create(owner=self.owner, result=revoked, result_id_snapshot=revoked.id, grant_source="legacy", revoked_at=timezone.now())
        missing = self.result()
        output = io.StringIO()
        call_command("reconcile_pricing_history", stdout=output)
        self.assertFalse(Entitlement.objects.filter(result=root).exists())
        self.assertFalse(Allowance.objects.filter(owner=self.owner).exists())
        for _ in range(2):
            call_command("reconcile_pricing_history", apply=True, operator=self.operator.email, reason="Reviewed historical cohort", stdout=io.StringIO())
        master.refresh_from_db()
        self.assertEqual(hashlib.sha256(master.file.read()).hexdigest(), master.sha256)
        self.assertEqual(Entitlement.objects.filter(result=root, revoked_at__isnull=True).count(), 1)
        self.assertFalse(Entitlement.objects.filter(result=revoked, revoked_at__isnull=True).exists())
        with Image.open(root.media.get(kind="preview").file) as image:
            self.assertEqual(image.size, (768, 576))
            self.assertEqual(image.getextrema(), ((96, 96),) * 3)
        missing.refresh_from_db()
        self.assertEqual(missing.status, "quarantined")
        self.assertEqual(pricing_for(self.owner)["free_used"], 3)

    def test_history_apply_refuses_undrained_legacy_jobs(self):
        Job.objects.create(owner=self.owner, project=self.project, operation="creation", state="queued", input_snapshot={}, deletion_epoch=0, estimated_cost_idr=0, next_run_at=timezone.now())
        with self.assertRaisesMessage(CommandError, "Drain or reconcile legacy jobs"):
            call_command("reconcile_pricing_history", apply=True, operator=self.operator.email, reason="Reviewed cohort", stdout=io.StringIO())
        self.assertFalse(Allowance.objects.filter(owner=self.owner).exists())

    def test_export_bounds_preserve_native_dimensions_and_limit_memory(self):
        self.assertEqual(export_dimensions(2048, 1536, "story"), (2052, 3648))
        with self.assertRaises(Exception) as error:
            export_dimensions(10000, 10000, "story")
        self.assertEqual(error.exception.code, "export_too_large")
