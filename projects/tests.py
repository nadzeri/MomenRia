import io
import tempfile
from datetime import timedelta
from pathlib import Path
from unittest.mock import patch

from PIL import Image
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import DatabaseError, transaction
from django.test import TestCase, override_settings
from django.utils import timezone

from accounts.models import User
from catalog.models import FaceSlot, Offer, TemplateVersion
from momenria.http import ApiError

from .models import Consent, SourceAsset
from .services import assign_source, create_project, undo_assignment, validate_and_store_source


class UploadValidationTests(TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.settings = override_settings(MEDIA_ROOT=self.tempdir.name, TOMBSTONE_ROOT=Path(self.tempdir.name) / "tombstones", PUBLIC_ACCESS=False, FACE_BLUR_THRESHOLD=0, FACE_MIN_BRIGHTNESS=0, FACE_MAX_BRIGHTNESS=255, FACE_MIN_SIZE_PX=40, STORAGE_MIN_FREE_BYTES=0, STORAGE_MAX_USED_PERCENT=100)
        self.settings.enable()
        self.user = User.objects.create_user("upload@example.com", "strong-password", email_verified=True)
        self.other = User.objects.create_user("other@example.com", "strong-password", email_verified=True)
        offer = Offer.objects.create(version=1, name="Uji", price_idr=19900, active=True)
        self.template = TemplateVersion.objects.create(slug="test", version=1, name="Test", occasion="Test", people_count=2, description="Test", sample_asset="app/assets/lebaran.png", configuration_hash="b"*64, generation_config={"max_cost_idr":1500}, status=TemplateVersion.Status.DRAFT, evidence_approved=True)
        self.slots = [FaceSlot.objects.create(template=self.template, position=index, x=.3 * index, y=.3) for index in (1, 2)]
        self.template.status = TemplateVersion.Status.PUBLISHED
        self.template.save(update_fields=("status",))
        self.project = create_project(self.user, self.template, offer)

    def tearDown(self):
        self.settings.disable()
        self.tempdir.cleanup()

    def test_multiple_face_photo_is_rejected_without_asset(self):
        image = Image.open("static/app/assets/lebaran.png")
        content = io.BytesIO(); image.save(content, "PNG")
        upload = SimpleUploadedFile("family.png", content.getvalue(), content_type="image/png")
        with self.assertRaisesMessage(Exception, "satu wajah saja"):
            validate_and_store_source(self.user, self.project.id, upload, "multi", "prd-v1", True)
        self.assertFalse(self.project.sources.exists())

    def test_declared_type_mismatch_is_rejected(self):
        image = Image.new("RGB", (300, 300), "white")
        content = io.BytesIO()
        image.save(content, "PNG")
        upload = SimpleUploadedFile("spoof.jpg", content.getvalue(), content_type="image/jpeg")
        with self.assertRaisesMessage(Exception, "nggak cocok"):
            validate_and_store_source(self.user, self.project.id, upload, "spoof", "prd-v1", True)

    def test_upload_api_rejects_unknown_multipart_fields_before_processing(self):
        self.client.force_login(self.user)
        upload = SimpleUploadedFile("face.jpg", b"not-an-image", content_type="image/jpeg")
        response = self.client.post(
            f"/api/v1/projects/{self.project.id}/sources",
            {"image": upload, "upload_key": "schema", "consent_version": "prd-v1", "consent_granted": "true", "unexpected": "value"},
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["code"], "invalid_fields")
        self.assertFalse(self.project.sources.exists())

    @override_settings(UPLOAD_MAX_PIXELS=100000)
    def test_pixel_limit_rejects_before_rgb_expansion(self):
        image = Image.new("RGB", (450, 300), "white")
        content = io.BytesIO()
        image.save(content, "PNG")
        upload = SimpleUploadedFile("large.png", content.getvalue(), content_type="image/png")
        with patch.object(Image.Image, "convert", side_effect=AssertionError("RGB expansion started")):
            with self.assertRaises(ApiError) as context:
                validate_and_store_source(self.user, self.project.id, upload, "large", "prd-v1", True)
        self.assertEqual(context.exception.code, "too_many_pixels")

    def test_other_owner_receives_not_found(self):
        self.client.force_login(self.other)
        response = self.client.get(f"/api/v1/projects/{self.project.id}")
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json()["code"], "not_found")

    def test_project_pagination_keeps_owner_scope_and_reaches_more_than_fifty(self):
        from .models import Project

        Project.objects.bulk_create([Project(owner=self.user, template=self.template, offer=self.project.offer) for _ in range(51)])
        Project.objects.create(owner=self.other, template=self.template, offer=self.project.offer)
        Project.objects.create(owner=self.user, template=self.template, offer=self.project.offer, state=Project.State.DELETED)
        self.client.force_login(self.user)
        first = self.client.get("/api/v1/projects?limit=100").json()
        self.assertEqual(len(first["items"]), 50)
        self.assertEqual(first["next_offset"], 50)
        second = self.client.get("/api/v1/projects?offset=50").json()
        self.assertEqual(len(second["items"]), 2)
        self.assertIsNone(second["next_offset"])
        self.assertEqual(len({item["id"] for item in first["items"] + second["items"]}), 52)
        self.assertIn("created_at", first["items"][0])
        self.assertIn("updated_at", first["items"][0])
        for query in ("offset=-1", "offset=abc", "offset=9223372036854775808", "limit=0", "limit=-1", "limit=abc"):
            self.assertEqual(self.client.get(f"/api/v1/projects?{query}").status_code, 400)

    def test_result_feedback_keeps_latest_per_slot_and_global_on_exact_version(self):
        from .models import Feedback, ResultVersion

        result = ResultVersion.objects.create(project=self.project, source_snapshot=[], region_snapshot=[], configuration_hash="b" * 64, kind=ResultVersion.Kind.CREATION, number=1, status=ResultVersion.Status.READY, expires_at=timezone.now() + timedelta(days=1))
        new_result = ResultVersion.objects.create(project=self.project, parent=result, source_snapshot=[], region_snapshot=[], configuration_hash="b" * 64, kind=ResultVersion.Kind.CORRECTION, number=2, status=ResultVersion.Status.READY, expires_at=result.expires_at)
        Feedback.objects.create(owner=self.user, result=result, slot=self.slots[0], accepted=True)
        latest = Feedback.objects.create(owner=self.user, result=result, slot=self.slots[0], accepted=False, issue="likeness")
        Feedback.objects.create(owner=self.user, result=result, slot=self.slots[1], accepted=None, issue="other")
        Feedback.objects.create(owner=self.user, result=result, accepted=False)
        global_latest = Feedback.objects.create(owner=self.user, result=result, accepted=True)
        self.client.force_login(self.user)
        versions = {item["id"]: item for item in self.client.get(f"/api/v1/projects/{self.project.id}").json()["results"]}
        reviews = {item["slot_id"]: item for item in versions[str(result.id)]["feedback"]}
        self.assertEqual(len(reviews), 3)
        self.assertEqual(reviews[str(self.slots[0].id)], {"slot_id": str(self.slots[0].id), "accepted": False, "issue": "likeness", "created_at": latest.created_at.isoformat()})
        self.assertEqual(reviews[None]["created_at"], global_latest.created_at.isoformat())
        self.assertTrue(reviews[None]["accepted"])
        self.assertEqual(versions[str(new_result.id)]["feedback"], [])
        self.client.force_login(self.other)
        self.assertEqual(self.client.get(f"/api/v1/projects/{self.project.id}").status_code, 404)
        self.assertEqual(self.client.post(f"/api/v1/results/{result.id}/feedback", {"accepted": True}, content_type="application/json").status_code, 404)

    def test_job_timestamps_match_durable_status(self):
        from processing.models import Job

        job = Job.objects.create(owner=self.user, project=self.project, operation=Job.Operation.CREATION, input_snapshot={}, deletion_epoch=0, estimated_cost_idr=0, next_run_at=timezone.now())
        self.client.force_login(self.user)
        payload = self.client.get(f"/api/v1/jobs/{job.id}").json()
        self.assertEqual(payload["created_at"], job.created_at.isoformat())
        self.assertEqual(payload["updated_at"], job.updated_at.isoformat())
        embedded = self.client.get(f"/api/v1/projects/{self.project.id}").json()["jobs"][0]
        self.assertEqual(embedded["updated_at"], payload["updated_at"])

    def test_delete_api_rejects_unknown_fields(self):
        self.client.force_login(self.user)
        response = self.client.delete(
            f"/api/v1/projects/{self.project.id}",
            {"confirmation": "DELETE", "password": "strong-password", "unexpected": True},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)
        self.project.refresh_from_db()
        self.assertNotEqual(self.project.state, self.project.State.DELETED)

    @override_settings(PUBLIC_ACCESS=True, PUBLIC_OWNER_EMAIL="upload@example.com")
    def test_public_owner_deletes_project_without_password(self):
        response = self.client.delete(
            f"/api/v1/projects/{self.project.id}",
            {"confirmation": "DELETE"},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 202)

    def test_slot_api_requires_boolean_move_and_exact_fields(self):
        consent = Consent.objects.create(project=self.project, owner=self.user, text_version="prd-v1", granted=True)
        source = SourceAsset.objects.create(
            project=self.project, consent=consent, upload_key="schema-slot", content_sha256="1" * 64,
            file="sources/schema-slot.jpg", original_name="face.jpg", format="JPEG", width=600, height=600,
            size_bytes=1000, status=SourceAsset.Status.READY, validation_code="fixture",
            expires_at=timezone.now() + timedelta(days=1),
        )
        self.client.force_login(self.user)
        response = self.client.put(
            f"/api/v1/projects/{self.project.id}/slots/{self.slots[0].id}",
            {"source_id": str(source.id), "expected_revision": self.project.revision, "move": "false"},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertFalse(self.project.assignments.exists())

    def test_published_template_is_database_immutable(self):
        with self.assertRaises(DatabaseError), transaction.atomic():
            TemplateVersion.objects.filter(id=self.template.id).update(name="Changed")

    def test_published_template_cannot_return_to_mutable_draft(self):
        with self.assertRaises(DatabaseError), transaction.atomic():
            TemplateVersion.objects.filter(id=self.template.id).update(status=TemplateVersion.Status.DRAFT)

    def test_deactivated_offer_remains_database_immutable(self):
        offer = Offer.objects.get(version=1)
        Offer.objects.filter(id=offer.id).update(active=False)
        with self.assertRaises(DatabaseError), transaction.atomic():
            Offer.objects.filter(id=offer.id).update(price_idr=1)

    def test_valid_upload_creates_owner_only_thumbnail(self):
        image = Image.open(Path(__file__).resolve().parent.parent / "static/app/assets/lebaran.png").convert("RGB")
        width, height = image.size
        crop = image.crop((int(.391 * width - 180), int(.241 * height - 180), int(.391 * width + 180), int(.241 * height + 180))).resize((720, 720))
        content = io.BytesIO()
        crop.save(content, "JPEG", quality=95)
        source = validate_and_store_source(self.user, self.project.id, SimpleUploadedFile("face.jpg", content.getvalue(), content_type="image/jpeg"), "thumbnail", "prd-v1", True)
        self.assertTrue(source.thumbnail.name)
        self.client.force_login(self.user)
        self.assertEqual(self.client.get(f"/api/v1/sources/{source.id}/thumbnail").status_code, 200)
        self.client.force_login(self.other)
        self.assertEqual(self.client.get(f"/api/v1/sources/{source.id}/thumbnail").status_code, 404)

    def test_duplicate_content_binds_new_upload_key_to_original_request(self):
        image = Image.open(Path(__file__).resolve().parent.parent / "static/app/assets/lebaran.png").convert("RGB")
        width, height = image.size

        def face_bytes(x, y):
            crop = image.crop((int(x * width - 180), int(y * height - 180), int(x * width + 180), int(y * height + 180))).resize((720, 720))
            content = io.BytesIO()
            crop.save(content, "JPEG", quality=95)
            return content.getvalue()

        first_bytes = face_bytes(.391, .241)
        second_bytes = face_bytes(.646, .308)
        first = validate_and_store_source(self.user, self.project.id, SimpleUploadedFile("first.jpg", first_bytes, content_type="image/jpeg"), "first-key", "prd-v1", True)
        duplicate = validate_and_store_source(self.user, self.project.id, SimpleUploadedFile("same.jpg", first_bytes, content_type="image/jpeg"), "retry-key", "prd-v1", True)
        self.assertEqual(duplicate.id, first.id)
        with self.assertRaises(ApiError) as context:
            validate_and_store_source(self.user, self.project.id, SimpleUploadedFile("different.jpg", second_bytes, content_type="image/jpeg"), "retry-key", "prd-v1", True)
        self.assertEqual(context.exception.code, "upload_key_conflict")

    def test_undo_restores_previous_unexpired_assignment(self):
        consent = Consent.objects.create(project=self.project, owner=self.user, text_version="prd-v1", granted=True)
        sources = [SourceAsset.objects.create(project=self.project, consent=consent, upload_key=f"undo-{index}", content_sha256=str(index) * 64, file=f"sources/undo-{index}.jpg", original_name="face.jpg", format="JPEG", width=600, height=600, size_bytes=1000, status=SourceAsset.Status.READY, validation_code="fixture", expires_at=timezone.now() + timedelta(days=1)) for index in (1, 2)]
        project = assign_source(self.user, self.project.id, self.slots[0].id, sources[0].id, self.project.revision)
        project = assign_source(self.user, project.id, self.slots[0].id, sources[1].id, project.revision)
        project = undo_assignment(self.user, project.id, project.revision)
        self.assertEqual(project.assignments.get(slot=self.slots[0]).source_id, sources[0].id)
