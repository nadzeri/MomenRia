import base64
import hashlib
import io
import json
import os
import tempfile
import threading
import uuid
from datetime import timedelta
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch

from PIL import Image
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import DatabaseError, connection, connections, close_old_connections, transaction
from django.test import TestCase, TransactionTestCase, override_settings
from django.utils import timezone

from accounts.models import User
from catalog.models import FaceSlot, Offer, TemplateVersion
from commerce.models import Order
from momenria.http import ApiError
from projects.models import Consent, MediaAsset, Project, ResultVersion, SlotAssignment, SourceAsset
from projects.result_services import create_greeting, frame_preview
from projects.services import assign_source, create_project, delete_project, validate_and_store_source
from operations.management.commands.maintenance import cleanup_orphan_media, reconcile_expired_leases

from .models import Job
from .services import admit_job
from .worker import claim_job, run_job


class TrialSlotModelTests(TestCase):
    def test_only_three_slots_can_be_granted(self):
        from django.db import IntegrityError
        from .models import Allowance
        owner = User.objects.create_user("slots@example.com", "strong-password")
        for number in (1, 2, 3):
            Allowance.objects.create(owner=owner, kind="creation", policy_version="three-free-v1", trial_slot=number)
        for number in (1, 4):
            with self.subTest(slot=number), self.assertRaises(IntegrityError), transaction.atomic():
                Allowance.objects.create(owner=owner, kind="creation", policy_version="three-free-v1", trial_slot=number)


class ProcessingFlowTests(TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.settings = override_settings(
            MEDIA_ROOT=self.tempdir.name, ADMISSION_ENABLED=True, DAILY_BUDGET_IDR=10000,
            TOMBSTONE_ROOT=Path(self.tempdir.name) / "tombstones",
            PUBLIC_ACCESS=False,
            AI_GATEWAY_MODE="fake", FACE_BLUR_THRESHOLD=0, FACE_MIN_BRIGHTNESS=0,
            FACE_MAX_BRIGHTNESS=255, FACE_MIN_SIZE_PX=40, STORAGE_MIN_FREE_BYTES=0,
            STORAGE_MAX_USED_PERCENT=100,
        )
        self.settings.enable()
        self.user = User.objects.create_user("owner@example.com", "strong-password", email_verified=True)
        self.other = User.objects.create_user("other@example.com", "strong-password", email_verified=True)
        self.offer = Offer.objects.create(version=1, name="Uji", price_idr=19900, active=True)
        self.template = TemplateVersion.objects.create(
            slug="lebaran", version=1, name="Lebaran", occasion="Lebaran", people_count=2,
            description="Test", sample_asset="app/assets/lebaran.png", configuration_hash="a" * 64,
            generation_config={"model":"fake", "max_cost_idr":1500}, status=TemplateVersion.Status.DRAFT,
            evidence_approved=True,
        )
        self.slots = [FaceSlot.objects.create(template=self.template, position=index, x=x, y=y) for index, (x, y) in enumerate(((.391,.241),(.646,.308)), 1)]
        self.template.status = TemplateVersion.Status.PUBLISHED
        self.template.save(update_fields=("status",))
        self.project = create_project(self.user, self.template, self.offer)

    def tearDown(self):
        self.settings.disable()
        self.tempdir.cleanup()

    def upload_face(self, slot, face_index, offset=0):
        source_image = Image.open(Path(__file__).resolve().parent.parent / "static/app/assets/lebaran.png").convert("RGB")
        x, y = ((.391,.241),(.646,.308))[face_index]
        width, height = source_image.size
        crop = source_image.crop((int(x*width-180+offset), int(y*height-180), int(x*width+180+offset), int(y*height+180))).resize((720,720))
        content = io.BytesIO()
        crop.save(content, "JPEG", quality=95)
        upload = SimpleUploadedFile(f"face-{face_index}.jpg", content.getvalue(), content_type="image/jpeg")
        source = validate_and_store_source(self.user, self.project.id, upload, str(uuid.uuid4()), "prd-v1", True)
        self.project.refresh_from_db()
        self.project = assign_source(self.user, self.project.id, slot.id, source.id, self.project.revision)

    def prepare(self):
        for index, slot in enumerate(self.slots):
            self.upload_face(slot, index)

    def test_three_successful_creations_exhaust_quota_even_after_deletion(self):
        from .quota import pricing_for
        self.prepare()
        for number in range(3):
            admit_job(self.user, self.project.id, Job.Operation.CREATION, self.project.revision, f"trial-{number}")
            self.assertTrue(run_job(claim_job()))
            self.project.refresh_from_db()
            self.assertEqual(pricing_for(self.user)["free_used"], number + 1)
        with self.assertRaises(ApiError) as error:
            admit_job(self.user, self.project.id, Job.Operation.CREATION, self.project.revision, "fourth")
        self.assertEqual(error.exception.status, 402)
        self.assertEqual(error.exception.code, "payment_required")
        delete_project(self.user, self.project.id)
        self.assertEqual(pricing_for(self.user)["free_remaining"], 0)

    def test_confirmed_failed_trial_releases_slot_and_uncertain_trial_holds_it(self):
        from .quota import pricing_for
        from .services import release_failed_job
        self.prepare()
        job, _ = admit_job(self.user, self.project.id, "creation", self.project.revision, "failed-trial")
        self.assertEqual(pricing_for(self.user)["free_reserved"], 1)
        release_failed_job(job, "confirmed_failure")
        self.assertEqual(pricing_for(self.user)["free_remaining"], 3)
        retry, _ = admit_job(self.user, self.project.id, "creation", self.project.revision, "retry-trial")
        self.assertEqual(retry.allowance_id, job.allowance_id)
        Job.objects.filter(pk=retry.pk).update(state="uncertain")
        self.assertEqual(pricing_for(self.user)["free_reserved"], 1)

    @override_settings(PAYMENT_PROVIDER="fake", PAYMENT_CHECKOUT_ENABLED=True)
    def test_paid_generation_order_freezes_inputs_before_payment(self):
        from commerce.api import order_json
        from commerce.services import create_generation_order
        from .models import Allowance
        from .quota import initialize_trial_allowances
        self.prepare()
        initialize_trial_allowances(self.user)
        Allowance.objects.filter(owner=self.user, trial_slot__isnull=False).update(consumed_at=timezone.now())
        offer = Offer.objects.get(purchase_unit="generation")
        offer.active = True
        offer.save()
        data = {"offer_id": str(offer.id), "expected_revision": self.project.revision, "terms_version": "2026-10-10", "refund_policy_version": "2026-10-10", "policies_accepted": True}
        order, created = create_generation_order(self.user, self.project.id, data, "paid-generation")
        self.assertTrue(created)
        self.assertEqual(order.amount_idr, 9900)
        self.assertEqual(order.job.state, "awaiting_payment")
        self.assertIsNone(claim_job())
        self.assertIsNone(order_json(order)["result_id"])
        self.assertEqual(order_json(order)["job_state"], "awaiting_payment")
        self.assertIsNone(order_json(order)["download_url"])
        self.assertIsNotNone(order.policies_accepted_at)
        replay, created = create_generation_order(self.user, self.project.id, data, "paid-generation")
        self.assertFalse(created)
        self.assertEqual(replay.id, order.id)
        self.assertEqual(self.project.jobs.count(), 1)
        with override_settings(PAYMENT_CHECKOUT_ENABLED=False, TERMS_VERSION="new-policy"):
            replay, created = create_generation_order(self.user, self.project.id, data, "paid-generation")
            self.assertFalse(created)
            self.assertEqual(replay.id, order.id)
        with self.assertRaises(ApiError) as error:
            assign_source(self.user, self.project.id, self.slots[0].id, self.project.assignments.first().source_id, self.project.revision)
        self.assertEqual(error.exception.code, "project_frozen")

    @override_settings(PAYMENT_PROVIDER="fake", PAYMENT_CHECKOUT_ENABLED=True)
    def test_paid_api_rejects_unaccepted_stale_and_client_priced_requests(self):
        self.prepare()
        offer = Offer.objects.get(purchase_unit="generation")
        offer.active = True
        offer.save()
        self.client.force_login(self.user)
        data = {"offer_id": str(offer.id), "expected_revision": self.project.revision, "terms_version": "2026-10-10", "refund_policy_version": "2026-10-10", "policies_accepted": True}
        for changes, expected in (({"policies_accepted": False}, 400), ({"terms_version": "old"}, 409), ({"amount_idr": 1}, 400), ({"expected_revision": True}, 400)):
            response = self.client.post(f"/api/v1/projects/{self.project.id}/generation-orders", {**data, **changes}, content_type="application/json", HTTP_IDEMPOTENCY_KEY=str(uuid.uuid4()))
            self.assertEqual(response.status_code, expected)
        response = self.client.post(f"/api/v1/projects/{self.project.id}/generation-orders", data, content_type="application/json", HTTP_IDEMPOTENCY_KEY="early-purchase")
        self.assertEqual(response.json()["code"], "free_pictures_available")
        self.assertFalse(self.project.jobs.exists())
        self.assertFalse(self.project.orders.exists())

    def prepare_paid_order(self):
        from commerce.services import create_generation_order
        from .models import Allowance
        from .quota import initialize_trial_allowances
        self.prepare()
        initialize_trial_allowances(self.user)
        Allowance.objects.filter(owner=self.user, trial_slot__isnull=False).update(consumed_at=timezone.now())
        offer = Offer.objects.get(purchase_unit="generation")
        offer.active = True
        offer.save()
        data = {"offer_id": str(offer.id), "expected_revision": self.project.revision, "terms_version": "2026-10-10", "refund_policy_version": "2026-10-10", "policies_accepted": True}
        return create_generation_order(self.user, self.project.id, data, f"paid-flow-{self.project.id}")[0]

    @override_settings(PAYMENT_PROVIDER="fake", PAYMENT_CHECKOUT_ENABLED=True)
    def test_refund_before_result_does_not_cancel_another_paid_picture(self):
        from commerce.services import record_refund_outcome, request_refund, settle_order
        order = self.prepare_paid_order()
        settle_order(order, "TX-NO-RESULT")
        self.project = create_project(self.user, self.template, self.offer)
        other = self.prepare_paid_order()
        operator = User.objects.create_superuser("refund-before-result@example.com", "test-password")
        refund, _ = request_refund(operator, order.id, "Customer remedy before dispatch", "refund-before-result")
        record_refund_outcome(operator, refund.id, outcome="succeeded", amount_idr=9900, reference="REF-NO-RESULT", evidence="Verified completed full refund", reason="Approved customer remedy before dispatch")
        order.job.refresh_from_db()
        other.job.refresh_from_db()
        self.assertEqual(order.job.state, "cancelled")
        self.assertEqual(other.job.state, "awaiting_payment")

    @override_settings(PAYMENT_PROVIDER="fake", PAYMENT_CHECKOUT_ENABLED=True)
    def test_payment_queues_one_job_and_completion_grants_one_download(self):
        from commerce.models import Entitlement
        from commerce.services import settle_order
        order = self.prepare_paid_order()
        self.assertIsNone(claim_job())
        with override_settings(PAYMENT_CHECKOUT_ENABLED=False):
            settle_order(order, "TX-PAID", {"test": True})
            settle_order(order, "TX-PAID", {"test": True})
        order.job.refresh_from_db()
        self.assertEqual(order.job.state, "queued")
        self.assertFalse(Entitlement.objects.filter(order=order).exists())
        self.assertTrue(run_job(claim_job()))
        order.refresh_from_db()
        self.assertEqual(order.fulfillment_state, "downloadable")
        self.assertIsNotNone(order.result_id)
        self.assertEqual(Entitlement.objects.filter(order=order).count(), 1)
        self.assertIsNone(claim_job())
        self.client.force_login(self.user)
        self.assertEqual(self.client.get(f"/api/v1/results/{order.result_id}/master").status_code, 200)

    def test_worker_rejects_creation_without_valid_trial_reservation(self):
        from .models import AllowanceReservation
        self.prepare()
        job, _ = admit_job(self.user, self.project.id, "creation", self.project.revision, "invalid-trial")
        AllowanceReservation.objects.filter(job=job).delete()
        self.assertFalse(run_job(claim_job()))
        job.refresh_from_db()
        self.assertEqual(job.error_code, "generation_not_authorized")
        self.assertFalse(self.project.results.exists())

    @override_settings(PAYMENT_PROVIDER="fake", PAYMENT_CHECKOUT_ENABLED=True)
    def test_late_payment_after_deletion_opens_one_refund_without_dispatch(self):
        from commerce.services import settle_order
        order = self.prepare_paid_order()
        delete_project(self.user, self.project.id)
        settle_order(order, "TX-LATE", {"test": True})
        settle_order(order, "TX-LATE", {"test": True})
        order.refresh_from_db()
        self.assertEqual(order.payment_state, "paid")
        self.assertEqual(order.refunds.count(), 1)
        self.assertEqual(order.refunds.get().amount_idr, 9900)
        self.assertIsNone(claim_job())
        self.assertFalse(self.project.results.exists())

    @override_settings(PAYMENT_PROVIDER="fake", PAYMENT_CHECKOUT_ENABLED=True)
    def test_confirmed_paid_failure_opens_refund_but_uncertain_failure_holds(self):
        from commerce.services import settle_order
        from .worker import WorkerFailure
        order = self.prepare_paid_order()
        settle_order(order, "TX-FAIL", {"test": True})
        with patch("processing.worker._generate", side_effect=WorkerFailure("provider_timeout", uncertain=True)):
            self.assertFalse(run_job(claim_job()))
        self.assertFalse(order.refunds.exists())
        order.job.refresh_from_db()
        self.assertEqual(order.job.state, "uncertain")
        from .services import release_failed_job
        release_failed_job(order.job, "confirmed_non_delivery")
        release_failed_job(order.job, "confirmed_non_delivery")
        self.assertEqual(order.refunds.count(), 1)

    @override_settings(PAYMENT_PROVIDER="midtrans", PAYMENT_CHECKOUT_ENABLED=True, PAYMENT_SERVER_KEY="server-key", PAYMENT_QRIS_ACQUIRER="gopay", AI_GATEWAY_MODE="9router")
    def test_qris_charge_uses_stored_price_and_keeps_validated_instructions(self):
        from commerce.api import order_json
        from commerce.services import apply_provider_status
        sent = []

        def gateway(method, path, payload=None):
            sent.append((method, path, payload))
            return {"order_id": payload["transaction_details"]["order_id"], "transaction_id": "TX-CORE", "gross_amount": "9900.00", "currency": "IDR", "payment_type": "qris", "fraud_status": "accept", "transaction_status": "pending", "status_code": "201", "actions": [{"name": "generate-qr-code", "method": "GET", "url": "https://api.sandbox.midtrans.com/v2/qris/TX-CORE/qr-code"}]}

        with patch("commerce.services._midtrans_request", side_effect=gateway, create=True):
            order = self.prepare_paid_order()
        self.assertEqual(len(sent), 1)
        self.assertEqual(sent[0][0:2], ("POST", "/v2/charge"))
        self.assertEqual(sent[0][2]["transaction_details"], {"order_id": order.merchant_reference, "gross_amount": 9900})
        self.assertEqual(order.payment_state, "pending")
        self.assertEqual(order_json(order)["payment_instructions"]["qr_url"], "https://api.sandbox.midtrans.com/v2/qris/TX-CORE/qr-code")
        status = {"order_id": order.merchant_reference, "transaction_id": "TX-CORE", "gross_amount": "9900.00", "currency": "IDR", "payment_type": "qris", "fraud_status": "accept", "transaction_status": "pending", "status_code": "201"}
        apply_provider_status(order, status)
        order.refresh_from_db()
        self.assertIn("qr_url", order_json(order)["payment_instructions"])

    @override_settings(PAYMENT_PROVIDER="midtrans", PAYMENT_CHECKOUT_ENABLED=True, PAYMENT_SERVER_KEY="server-key", PAYMENT_QRIS_ACQUIRER="gopay", AI_GATEWAY_MODE="9router")
    def test_charge_timeout_retains_order_and_only_retries_after_status_lookup(self):
        from commerce.services import refresh_order
        attempts = []

        def gateway(method, path, payload=None):
            attempts.append((method, path, payload))
            raise ApiError(503, "payment_status_unavailable", "Timeout")

        with patch("commerce.services._midtrans_request", side_effect=gateway, create=True):
            order = self.prepare_paid_order()
            self.assertEqual(order.payment_state, "uncertain")
            with self.assertRaises(ApiError):
                refresh_order(order)
        self.assertEqual([item[0] for item in attempts], ["POST", "GET"])
        self.assertEqual(self.project.orders.count(), 1)
        self.assertEqual(self.project.jobs.get().state, "awaiting_payment")

    @override_settings(PAYMENT_PROVIDER="fake", PAYMENT_CHECKOUT_ENABLED=True)
    def test_expired_unpaid_order_releases_prepared_capacity(self):
        from operations.management.commands.maintenance import reconcile_payments
        order = self.prepare_paid_order()
        Order.objects.filter(pk=order.pk).update(expires_at=timezone.now() - timedelta(seconds=1))
        reconcile_payments(timezone.now())
        order.refresh_from_db()
        order.job.refresh_from_db()
        self.assertEqual(order.payment_state, "expired")
        self.assertEqual(order.job.state, "cancelled")
        self.assertEqual(order.job.budget_reservation.state, "released")

    def test_preview_thumbnail_and_greeting_have_no_brand_watermark(self):
        from .worker import _preview
        flat = Image.new("RGB", (2048, 1536), (96, 96, 96))
        self.assertEqual(_preview(flat).getextrema(), ((96, 96), (96, 96), (96, 96)))
        self.prepare()
        job, _ = admit_job(self.user, self.project.id, "creation", self.project.revision, "clean-result")
        with patch("processing.worker._generate", return_value=(flat, True, "fake-test", "")):
            run_job(claim_job())
        job.refresh_from_db()
        self.project.refresh_from_db()
        greeting = create_greeting(self.user, job.result_id, "", self.project.revision)
        preview = greeting.media.get(kind=MediaAsset.Kind.PREVIEW)
        with preview.file.open("rb") as file, Image.open(file) as image:
            self.assertEqual(image.getextrema(), ((96, 96), (96, 96), (96, 96)))

    def test_free_original_download_and_compatibility_download_match_master_bytes(self):
        self.prepare()
        job, _ = admit_job(self.user, self.project.id, "creation", self.project.revision, "full-download")
        run_job(claim_job())
        job.refresh_from_db()
        master = job.result.media.get(kind=MediaAsset.Kind.MASTER)
        self.client.force_login(self.user)
        for suffix in ("master", "preview?download=1"):
            response = self.client.get(f"/api/v1/results/{job.result_id}/{suffix}")
            self.assertEqual(response.status_code, 200)
            data = b"".join(response.streaming_content)
            self.assertEqual(hashlib.sha256(data).hexdigest(), master.sha256)
            self.assertEqual(Image.open(io.BytesIO(data)).size, (2048, 1536))

    def test_correction_and_greeting_download_inherit_root_access_and_revocation(self):
        from commerce.models import Entitlement
        self.prepare()
        job, _ = admit_job(self.user, self.project.id, "creation", self.project.revision, "root-access")
        run_job(claim_job())
        job.refresh_from_db()
        self.project.refresh_from_db()
        correction, _ = admit_job(self.user, self.project.id, "correction", self.project.revision, "derived-access", parent_result_id=job.result_id, target_slot_id=self.slots[0].id, correction_action="enhance")
        run_job(claim_job())
        correction.refresh_from_db()
        self.project.refresh_from_db()
        greeting = create_greeting(self.user, correction.result_id, "Selamat", self.project.revision)
        self.client.force_login(self.user)
        for result_id in (job.result_id, correction.result_id, greeting.id):
            self.assertEqual(self.client.get(f"/api/v1/results/{result_id}/master").status_code, 200)
        Entitlement.objects.filter(result_id_snapshot=job.result_id).update(revoked_at=timezone.now())
        for result_id in (job.result_id, correction.result_id, greeting.id):
            for suffix in ("master", "preview", "preview?download=1", "preview?download=1&format=story"):
                self.assertIn(self.client.get(f"/api/v1/results/{result_id}/{suffix}").status_code, (403, 404))





    def test_legacy_consumed_allowance_counts_toward_lifetime_limit(self):
        from .models import Allowance, AllowanceReservation

        self.prepare()
        previous_project = create_project(self.user, self.template, self.offer)
        allowance = Allowance.objects.create(owner=self.user, kind=Allowance.Kind.CREATION, policy_version="v1", consumed_at=timezone.now())
        previous_job = Job.objects.create(owner=self.user, project=previous_project, allowance=allowance, operation=Job.Operation.CREATION, state=Job.State.READY, input_snapshot={}, deletion_epoch=0, estimated_cost_idr=0, next_run_at=timezone.now())
        AllowanceReservation.objects.create(allowance=allowance, job=previous_job)
        self.client.force_login(self.user)
        self.assertTrue(self.client.get("/api/v1/session").json()["creation_available"])
        for number in range(2):
            revision = self.project.revision
            key = f"lifetime-creation-{number}"
            job, created = admit_job(self.user, self.project.id, Job.Operation.CREATION, revision, key)
            self.assertTrue(created)
            self.assertIsNotNone(job.allowance_id)
            replay, created = admit_job(self.user, self.project.id, Job.Operation.CREATION, revision, key)
            self.assertFalse(created)
            self.assertEqual(replay.id, job.id)
            with self.assertRaises(ApiError) as context:
                admit_job(self.user, self.project.id, Job.Operation.CREATION, revision, f"{key}-duplicate")
            self.assertEqual(context.exception.code, "job_active")
            self.assertTrue(run_job(claim_job()))
            job.refresh_from_db()
            self.assertEqual(job.state, Job.State.READY)
            self.project.refresh_from_db()
        with self.assertRaises(ApiError) as error:
            admit_job(self.user, self.project.id, Job.Operation.CREATION, self.project.revision, "fourth-unpaid")
        self.assertEqual(error.exception.code, "payment_required")
        self.assertEqual(self.project.results.count(), 2)
        allowance.refresh_from_db()
        self.assertIsNotNone(allowance.consumed_at)
        self.assertTrue(AllowanceReservation.objects.filter(job=previous_job).exists())

    def start_9router(self, response_body=None):
        response_image = Image.open(Path(__file__).resolve().parent.parent / "static/app/assets/lebaran.png").convert("RGB").resize((2048, 1536))
        response_buffer = io.BytesIO()
        response_image.save(response_buffer, "JPEG", quality=95)
        received = []

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                body = self.rfile.read(int(self.headers["Content-Length"]))
                received.append((self.path, dict(self.headers), json.loads(body)))
                payload = json.dumps(response_body if response_body is not None else {"id": "req-9router-1", "model": "provider/portrait-v1", "data": [{"b64_json": base64.b64encode(response_buffer.getvalue()).decode()}]}).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)

            def log_message(self, format, *args):
                return

        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        thread = threading.Thread(target=server.serve_forever)
        thread.start()
        return server, thread, received

    def configure_character_template(self, **overrides):
        people_count = overrides.pop("people_count", 2)
        config = {
            "prompt_version": "character-v1", "identity_strategy": "originals",
            "scene": "A family beside a sunlit window.", "wardrobe_policy": "Blue formal clothing.",
            "model": "provider/pinned-portrait", "gateway_path": "/images/generations",
            "max_cost_idr": 1500, "reference_max_images": 9,
        }
        config.update(overrides)
        self.template = TemplateVersion.objects.create(
            slug="character", version=1, name="Character portrait", occasion="Test", people_count=people_count,
            description="Test", sample_asset="app/assets/lebaran.png", configuration_hash="c" * 64,
            generation_config=config, evidence_approved=True,
        )
        self.slots = [FaceSlot.objects.create(template=self.template, position=i, x=x, y=y) for i, (x, y) in enumerate(((.391, .241), (.646, .308), (.2, .65), (.8, .65))[:people_count], 1)]
        self.template.status = TemplateVersion.Status.PUBLISHED
        self.template.save(update_fields=("status",))
        self.project.template = self.template
        self.project.save(update_fields=("template",))

    def test_character_prompt_freezes_scene_mapping_and_model_at_admission(self):
        from .worker import _generation_prompt

        self.configure_character_template()
        self.prepare()
        job, _ = admit_job(self.user, self.project.id, Job.Operation.CREATION, self.project.revision, "frozen-prompt")
        self.assertIn("prompt", job.input_snapshot)
        prompt = job.input_snapshot["prompt"]
        self.assertIn("A family beside a sunlit window.", prompt)
        self.assertIn("Blue formal clothing.", prompt)
        self.assertIn(str(self.slots[0].id), prompt)
        self.assertIn("PERSON_2_PRIMARY", prompt)
        self.assertNotIn("Indonesian appearance", prompt)
        self.assertEqual(job.input_snapshot["model"], "provider/pinned-portrait")
        self.assertEqual([item["role"] for item in job.input_snapshot["image_roles"]], ["template", "primary", "primary"])
        job.refresh_from_db()
        job.project.template.generation_config = {"scene": "Changed after dispatch"}
        with override_settings(NINE_ROUTER_GENERATION_MODEL="changed-model"):
            self.assertEqual(_generation_prompt(job), prompt)

    def test_character_reference_limit_rejects_without_reserving_a_job(self):
        self.configure_character_template(reference_max_images=2)
        self.prepare()
        with self.assertRaises(ApiError) as context:
            admit_job(self.user, self.project.id, Job.Operation.CREATION, self.project.revision, "too-many-images")
        self.assertEqual(context.exception.code, "reference_limit_exceeded")
        self.assertFalse(self.project.jobs.exists())

    def test_production_character_configuration_requires_current_recipe_and_capability_evidence(self):
        from .prompts import recipe_digest, validate_character_configuration
        from .services import canonical_hash

        self.configure_character_template()
        with override_settings(APP_ENV="production"):
            with self.assertRaises(ApiError) as missing:
                validate_character_configuration(self.template)
            self.assertEqual(missing.exception.code, "gateway_contract_unverified")
            self.template.generation_config.update(capability_verified=True, capability_version="contract-20260926", recipe_digest=recipe_digest())
            with self.assertRaises(ApiError) as stale:
                validate_character_configuration(self.template)
            self.assertEqual(stale.exception.code, "configuration_unverified")
            self.template.configuration_hash = canonical_hash(self.template.generation_config)
            validate_character_configuration(self.template)

    def test_manifest_handles_one_through_four_people_without_losing_slot_identity(self):
        from types import SimpleNamespace
        from .prompts import freeze_portrait_prompt

        for count in range(1, 5):
            slots = [{"id": str(uuid.uuid4()), "position": position, "x": 1 - position / 5, "y": .4, "width": .12, "height": .16} for position in range(1, count + 1)]
            snapshot = {"generation_config": {"prompt_version": "character-v1", "model": "test", "gateway_path": "/images/generations", "reference_max_images": 5}, "slots": slots, "sources": [{"source_id": str(uuid.uuid4()), "slot_id": slot["id"]} for slot in slots]}
            template = SimpleNamespace(generation_config=snapshot["generation_config"], sample_asset="test.jpg", sample_sha256="a" * 64, people_count=count, description="Scene", attire="Wardrobe")
            freeze_portrait_prompt(snapshot, template, "creation")
            self.assertEqual(len(snapshot["image_roles"]), count + 1)
            for position, slot in enumerate(slots, 1):
                self.assertIn(f"PERSON_{position} belongs to slot {slot['id']}, center ({slot['x']}, 0.4)", snapshot["prompt"])
                self.assertEqual(snapshot["image_roles"][position]["slot_id"], slot["id"])

    def test_four_person_manifest_uses_all_nine_images_in_slot_order(self):
        from .worker import _gateway_images

        self.configure_character_template(people_count=4, identity_strategy="source_layout")
        for index, slot in enumerate(self.slots):
            self.upload_face(slot, index % 2, offset=10 * (index // 2))
        job, _ = admit_job(self.user, self.project.id, Job.Operation.CREATION, self.project.revision, "four-person-manifest")
        images = _gateway_images(job)
        self.assertEqual(len(images), 9)
        for index, source in enumerate(job.input_snapshot["sources"]):
            self.assertEqual(hashlib.sha256(base64.b64decode(images[index * 2 + 1].split(",", 1)[1])).hexdigest(), source["sha256"])
            self.assertEqual(hashlib.sha256(base64.b64decode(images[index * 2 + 2].split(",", 1)[1])).hexdigest(), source["character_sheet"]["sha256"])
        self.assertIn(f"PERSON_3 belongs to slot {self.slots[2].id}, center (0.20000, 0.65000)", job.input_snapshot["prompt"])

    def test_source_character_sheet_is_cached_private_and_expires_with_original(self):
        self.configure_character_template(identity_strategy="source_layout")
        self.prepare()
        source = self.project.assignments.get(slot=self.slots[0]).source
        self.client.force_login(self.user)
        payload = {"source_id": str(source.id), "mode": "source_layout", "expected_revision": self.project.revision}
        response = self.client.post(f"/api/v1/projects/{self.project.id}/character-sheets", payload, content_type="application/json")
        self.assertEqual(response.status_code, 200)
        sheet = response.json()["sheet"]
        self.assertEqual(sheet["status"], "approved")
        self.assertEqual(sheet["expires_at"], source.expires_at.isoformat())
        repeated = self.client.post(f"/api/v1/projects/{self.project.id}/character-sheets", payload, content_type="application/json")
        self.assertEqual(repeated.json()["sheet"]["id"], sheet["id"])
        preview = self.client.get(sheet["preview_url"])
        self.assertEqual(preview.status_code, 200)
        self.assertEqual(preview["Cache-Control"], "private, no-store")
        image = Image.open(io.BytesIO(b"".join(preview.streaming_content)))
        self.assertEqual(image.size, (1536, 1024))
        self.client.force_login(self.other)
        self.assertEqual(self.client.get(sheet["preview_url"]).status_code, 404)
        self.client.force_login(self.user)
        SourceAsset.objects.filter(pk=source.pk).update(expires_at=timezone.now() - timedelta(seconds=1))
        self.assertEqual(self.client.get(sheet["preview_url"]).status_code, 404)

    def test_source_layout_clamps_face_crop_at_both_image_edges(self):
        from projects.character_sheets import build_source_sheet

        self.configure_character_template()
        self.prepare()
        for source, detected in zip(self.project.sources.order_by("uploaded_at"), ([-5, -5, 100, 100], [650, 650, 100, 100])):
            with patch("projects.services.detect_faces", return_value=[detected]):
                sheet = build_source_sheet(self.project, source)
            left, top, right, bottom = sheet.panel_provenance[1]["bounds"]
            self.assertTrue(0 <= left < right <= source.width)
            self.assertTrue(0 <= top < bottom <= source.height)
            with sheet.file.open("rb") as file, Image.open(file) as image:
                self.assertEqual(image.size, (1536, 1024))

    def test_generated_review_rejects_other_owner_stale_revision_and_replaced_source(self):
        from .services import admit_character_sheet

        self.configure_character_template(identity_strategy="generated_optional", generated_sheets_enabled=True, sheet_max_cost_idr=500)
        self.prepare()
        source = self.project.assignments.get(slot=self.slots[0]).source
        sheet, _, _ = admit_character_sheet(self.user, self.project.id, source.id, self.project.revision, "review-guards")
        old_revision = self.project.revision
        self.assertTrue(run_job(claim_job()))
        self.project.refresh_from_db()
        endpoint = f"/api/v1/character-sheets/{sheet.id}/review"
        self.client.force_login(self.other)
        response = self.client.post(endpoint, {"decision": "approve", "expected_revision": self.project.revision}, content_type="application/json")
        self.assertEqual(response.status_code, 404)
        self.client.force_login(self.user)
        response = self.client.post(endpoint, {"decision": "approve", "expected_revision": old_revision}, content_type="application/json")
        self.assertEqual(response.json()["code"], "stale_revision")
        self.upload_face(self.slots[0], 0, offset=10)
        response = self.client.post(endpoint, {"decision": "approve", "expected_revision": self.project.revision}, content_type="application/json")
        self.assertEqual(response.json()["code"], "source_not_assigned")
        sheet.refresh_from_db()
        self.assertEqual(sheet.status, "review")
        self.assertIsNone(sheet.approved_at)

    def test_assignment_rejects_another_sources_sheet_and_undo_restores_matching_sheet(self):
        from projects.services import undo_assignment

        self.configure_character_template(identity_strategy="source_layout")
        self.prepare()
        self.client.force_login(self.user)
        details = self.client.get(f"/api/v1/projects/{self.project.id}").json()
        self.assertIn("character_sheets", details)
        assignments = list(self.project.assignments.order_by("slot__position"))
        first, second = assignments
        invalid = self.client.put(f"/api/v1/projects/{self.project.id}/slots/{first.slot_id}", {
            "source_id": str(first.source_id), "character_sheet_id": str(second.character_sheet_id),
            "expected_revision": self.project.revision,
        }, content_type="application/json")
        self.assertEqual(invalid.status_code, 409)
        self.assertEqual(invalid.json()["code"], "sheet_source_mismatch")
        moved = assign_source(self.user, self.project.id, first.slot_id, second.source_id, self.project.revision, move=True)
        restored = undo_assignment(self.user, self.project.id, moved.revision)
        self.assertEqual(restored.assignments.get(slot=first.slot).character_sheet_id, first.character_sheet_id)
        self.assertEqual(restored.assignments.get(slot=second.slot).character_sheet_id, second.character_sheet_id)

    def test_character_manifest_matches_images_and_deleted_sheets_are_removed(self):
        from .worker import _gateway_images
        from operations.management.commands.maintenance import process_deletions

        self.configure_character_template(identity_strategy="source_layout", reference_order="identity_first")
        self.prepare()
        job, _ = admit_job(self.user, self.project.id, Job.Operation.CREATION, self.project.revision, "sheet-manifest")
        self.assertEqual([role["role"] for role in job.input_snapshot["image_roles"]], ["primary", "sheet", "primary", "sheet", "template"])
        images = _gateway_images(job)
        self.assertEqual(len(images), 5)
        first = base64.b64decode(images[0].split(",", 1)[1])
        self.assertEqual(hashlib.sha256(first).hexdigest(), job.input_snapshot["sources"][0]["sha256"])
        sheet_paths = [Path(sheet.file.path) for sheet in self.project.character_sheets.all()]
        self.assertTrue(all(path.exists() for path in sheet_paths))
        delete_project(self.user, self.project.id)
        process_deletions(timezone.now())
        self.assertTrue(all(not path.exists() for path in sheet_paths))

    def test_generated_sheet_uses_original_requires_review_and_has_no_allowance(self):
        from .models import Allowance
        from .worker import _gateway_images

        self.configure_character_template(identity_strategy="generated_optional", generated_sheets_enabled=True, sheet_max_cost_idr=500)
        self.prepare()
        source = self.project.assignments.get(slot=self.slots[0]).source
        self.client.force_login(self.user)
        payload = {"source_id": str(source.id), "mode": "generated", "expected_revision": self.project.revision}
        response = self.client.post(f"/api/v1/projects/{self.project.id}/character-sheets", payload, content_type="application/json", HTTP_IDEMPOTENCY_KEY="generated-sheet")
        self.assertEqual(response.status_code, 202)
        sheet_id = response.json()["sheet"]["id"]
        job = Job.objects.get(id=response.json()["job"]["id"])
        self.assertIsNone(job.allowance_id)
        self.assertFalse(Allowance.objects.filter(owner=self.user).exists())
        images = _gateway_images(job)
        self.assertEqual(len(images), 1)
        self.assertEqual(hashlib.sha256(base64.b64decode(images[0].split(",", 1)[1])).hexdigest(), source.content_sha256)
        repeated = self.client.post(f"/api/v1/projects/{self.project.id}/character-sheets", payload, content_type="application/json", HTTP_IDEMPOTENCY_KEY="generated-sheet")
        self.assertEqual(repeated.json()["job"]["id"], str(job.id))
        self.assertTrue(run_job(claim_job()))
        self.project.refresh_from_db()
        sheet = self.project.character_sheets.get(id=sheet_id)
        self.assertEqual(sheet.status, "review")
        self.assertEqual(self.project.results.count(), 0)
        with self.assertRaises(ApiError) as context:
            assign_source(self.user, self.project.id, self.slots[0].id, source.id, self.project.revision, character_sheet_id=sheet.id)
        self.assertEqual(context.exception.code, "sheet_not_ready")
        review = self.client.post(f"/api/v1/character-sheets/{sheet.id}/review", {"decision": "approve", "expected_revision": self.project.revision}, content_type="application/json")
        self.assertEqual(review.status_code, 200)
        self.project.refresh_from_db()
        self.project = assign_source(self.user, self.project.id, self.slots[0].id, source.id, self.project.revision, character_sheet_id=sheet.id)
        portrait, _ = admit_job(self.user, self.project.id, Job.Operation.CREATION, self.project.revision, "after-sheet")
        self.assertEqual(portrait.input_snapshot["sources"][0]["character_sheet"]["id"], str(sheet.id))
        self.assertIsNotNone(portrait.allowance_id)

    def test_rejected_generated_sheet_has_only_one_explicit_retry(self):
        self.configure_character_template(identity_strategy="generated_optional", generated_sheets_enabled=True, sheet_max_cost_idr=500)
        self.prepare()
        source = self.project.assignments.get(slot=self.slots[0]).source
        self.client.force_login(self.user)
        for index in range(2):
            response = self.client.post(f"/api/v1/projects/{self.project.id}/character-sheets", {
                "source_id": str(source.id), "mode": "generated", "expected_revision": self.project.revision,
            }, content_type="application/json", HTTP_IDEMPOTENCY_KEY=f"sheet-retry-{index}")
            self.assertEqual(response.status_code, 202)
            self.assertTrue(run_job(claim_job()))
            self.project.refresh_from_db()
            sheet_id = response.json()["sheet"]["id"]
            review = self.client.post(f"/api/v1/character-sheets/{sheet_id}/review", {"decision": "reject", "expected_revision": self.project.revision}, content_type="application/json")
            self.assertEqual(review.status_code, 200)
            self.project.refresh_from_db()
        denied = self.client.post(f"/api/v1/projects/{self.project.id}/character-sheets", {
            "source_id": str(source.id), "mode": "generated", "expected_revision": self.project.revision,
        }, content_type="application/json", HTTP_IDEMPOTENCY_KEY="sheet-retry-2")
        self.assertEqual(denied.status_code, 409)
        self.assertEqual(denied.json()["code"], "sheet_attempt_limit")

    def test_completed_real_cost_stays_in_daily_budget(self):
        self.prepare()
        job, _ = admit_job(self.user, self.project.id, Job.Operation.CREATION, self.project.revision, "spent-first")
        job.state = Job.State.FAILED
        job.save(update_fields=("state",))
        reservation = job.budget_reservation
        reservation.state = reservation.State.RECONCILED
        reservation.actual = None
        reservation.save(update_fields=("state", "actual"))
        with override_settings(DAILY_BUDGET_IDR=int(reservation.estimate)):
            with self.assertRaises(ApiError) as context:
                admit_job(self.user, self.project.id, Job.Operation.CREATION, self.project.revision, "spent-second")
        self.assertEqual(context.exception.code, "budget_exhausted")

    def test_completed_sheet_bytes_and_source_are_database_immutable(self):
        from projects.models import CharacterSheet

        self.configure_character_template(identity_strategy="source_layout")
        self.prepare()
        sheet = self.project.character_sheets.first()
        for mutation in ({"sha256": "f" * 64}, {"input_snapshot": {}}, {"expires_at": sheet.expires_at + timedelta(days=1)}):
            with self.assertRaises(DatabaseError), transaction.atomic():
                CharacterSheet.objects.filter(pk=sheet.pk).update(**mutation)

    def test_completed_sheet_preparation_does_not_freeze_template_changes(self):
        from projects.services import change_template

        self.configure_character_template(identity_strategy="generated_optional", generated_sheets_enabled=True, sheet_max_cost_idr=500)
        self.prepare()
        self.client.force_login(self.user)
        source = self.project.assignments.first().source
        response = self.client.post(f"/api/v1/projects/{self.project.id}/character-sheets", {"source_id": str(source.id), "mode": "generated", "expected_revision": self.project.revision}, content_type="application/json", HTTP_IDEMPOTENCY_KEY="change-after-sheet")
        self.assertEqual(response.status_code, 202)
        self.assertTrue(run_job(claim_job()))
        self.project.refresh_from_db()
        old_sheet_ids = set(self.project.character_sheets.values_list("id", flat=True))
        original = TemplateVersion.objects.get(slug="lebaran")
        try:
            changed = change_template(self.user, self.project.id, original, self.project.revision, True)
        except ApiError as error:
            self.fail(f"Completed reference preparation must not freeze the draft: {error.code}")
        self.assertFalse(changed.assignments.exists())
        self.assertEqual(set(changed.character_sheets.values_list("id", flat=True)), old_sheet_ids)

    def test_stale_claim_cannot_dispatch_or_change_new_attempt(self):
        self.prepare()
        admit_job(self.user, self.project.id, Job.Operation.CREATION, self.project.revision, "stale-claim")
        stale = claim_job()
        Job.objects.filter(pk=stale.pk).update(leased_until=timezone.now() - timedelta(seconds=1))
        reconcile_expired_leases(timezone.now())
        current = claim_job()
        with patch("processing.worker._generate") as generate:
            self.assertFalse(run_job(stale))
        generate.assert_not_called()
        current.refresh_from_db()
        self.assertEqual(current.state, Job.State.DISPATCHING)
        self.assertEqual(current.attempts.order_by("-number").first().state, "prepared")

    def test_lease_maintenance_preserves_completion_before_lock(self):
        self.prepare()
        admit_job(self.user, self.project.id, Job.Operation.CREATION, self.project.revision, "lease-completion")
        job = claim_job()
        Job.objects.filter(pk=job.pk).update(leased_until=timezone.now() - timedelta(seconds=1))
        original_lock = Job.objects.select_for_update
        def finish_before_lock(*args, **kwargs):
            Job.objects.filter(pk=job.pk).update(state=Job.State.READY)
            return original_lock(*args, **kwargs)
        with patch("operations.management.commands.maintenance.Job.objects.select_for_update", side_effect=finish_before_lock):
            reconcile_expired_leases(timezone.now())
        job.refresh_from_db()
        self.assertEqual(job.state, Job.State.READY)

    def test_approved_generated_sheet_cannot_bypass_source_only_template(self):
        from projects.character_sheets import eligible_sheet
        from .services import admit_character_sheet

        self.configure_character_template(identity_strategy="generated_optional", generated_sheets_enabled=True, sheet_max_cost_idr=500)
        self.prepare()
        source = self.project.assignments.first().source
        sheet, _, _ = admit_character_sheet(self.user, self.project.id, source.id, self.project.revision, "gated-generated")
        self.assertTrue(run_job(claim_job()))
        type(sheet).objects.filter(pk=sheet.pk).update(status="approved", approved_at=timezone.now())
        self.project.template.generation_config = {"identity_strategy": "source_layout", "generated_sheets_enabled": False}
        with self.assertRaises(ApiError) as context:
            eligible_sheet(self.project, source, sheet.id)
        self.assertEqual(context.exception.code, "sheet_strategy_mismatch")

    def test_evaluation_plan_is_bounded_idempotent_and_counts_missing_feedback(self):
        from django.core.management import call_command
        from django.core.management.base import CommandError

        self.configure_character_template(identity_strategy="source_layout")
        self.prepare()
        manifest = Path(self.tempdir.name) / "evaluation.json"
        manifest.write_text(json.dumps({"schema": 1, "gateway_version": "stub-contract-test", "cases": [{"id": "case-1", "identity_set": "consented-set-1", "scene": "family", "repeat": 1, "arm": "D", "project_id": str(self.project.id)}]}))
        output = io.StringIO()
        call_command("evaluate_characters", str(manifest), stdout=output)
        report = json.loads(output.getvalue())
        self.assertEqual(report["arms"]["D"]["missing_feedback"], 2)
        self.assertFalse(self.project.jobs.exists())
        with self.assertRaises(CommandError):
            call_command("evaluate_characters", str(manifest), enqueue=True, max_calls=1, max_cost_idr=1, stdout=io.StringIO())
        options = {"enqueue": True, "max_calls": 10, "max_cost_idr": 10000, "stdout": io.StringIO()}
        call_command("evaluate_characters", str(manifest), **options)
        self.assertEqual(self.project.jobs.count(), 1)
        self.assertTrue(run_job(claim_job()))
        call_command("evaluate_characters", str(manifest), **options)
        self.assertEqual(self.project.jobs.count(), 1)
        self.client.force_login(self.user)
        result = self.project.results.get()
        self.client.post(f"/api/v1/results/{result.id}/feedback", {"accepted": True}, content_type="application/json")
        response = self.client.post(f"/api/v1/results/{result.id}/feedback", {"slot_id": str(self.slots[0].id), "issue": "wrong", "accepted": False}, content_type="application/json")
        self.assertEqual(response.status_code, 201)
        output = io.StringIO()
        call_command("evaluate_characters", str(manifest), stdout=output)
        report = json.loads(output.getvalue())
        self.assertEqual(report["arms"]["D"]["wrong_person_reports"], 1)
        self.assertEqual(report["arms"]["D"]["missing_feedback"], 1)
        self.assertEqual(report["arms"]["D"]["acceptance_all_faces"], 0)

    def test_late_sheet_timeout_cannot_revive_deleted_project(self):
        from .services import admit_character_sheet
        from .worker import WorkerFailure

        self.configure_character_template(identity_strategy="generated_optional", generated_sheets_enabled=True, sheet_max_cost_idr=500)
        self.prepare()
        sheet, job, _ = admit_character_sheet(self.user, self.project.id, self.project.assignments.first().source_id, self.project.revision, "late-sheet")
        def delete_during_request(*args):
            delete_project(self.user, self.project.id)
            raise WorkerFailure("gateway_transport_unknown", uncertain=True)
        with patch("processing.worker._generate", side_effect=delete_during_request):
            self.assertFalse(run_job(claim_job()))
        job.refresh_from_db()
        sheet.refresh_from_db()
        self.assertEqual(job.state, Job.State.CANCELLED)
        self.assertFalse(sheet.file)
        self.assertEqual(job.budget_reservation.state, "reserved")
        from operations.management.commands.maintenance import evaluate_alerts
        from operations.models import OperationalAlert

        evaluate_alerts(timezone.now())
        self.assertTrue(OperationalAlert.objects.get(code="uncertain_jobs").active)

    def test_late_completed_sheet_retains_cost_without_publishing_after_deletion(self):
        from .services import admit_character_sheet

        self.configure_character_template(identity_strategy="generated_optional", generated_sheets_enabled=True, sheet_max_cost_idr=500)
        self.prepare()
        sheet, job, _ = admit_character_sheet(self.user, self.project.id, self.project.assignments.first().source_id, self.project.revision, "late-completed-sheet")
        def finish_after_deletion(*args):
            delete_project(self.user, self.project.id)
            return Image.new("RGB", (1536, 1024)), False, "provider/model", "request-id"
        with patch("processing.worker._generate", side_effect=finish_after_deletion):
            self.assertFalse(run_job(claim_job()))
        job.refresh_from_db()
        sheet.refresh_from_db()
        self.assertEqual(job.state, Job.State.CANCELLED)
        self.assertFalse(sheet.file)
        self.assertEqual(job.budget_reservation.state, "reconciled")
        self.assertIsNone(job.budget_reservation.actual)
        self.assertTrue(job.attempts.get().provider_completed)

    def test_replacement_correction_uses_new_sheet_and_retains_prompt_provenance(self):
        self.configure_character_template(identity_strategy="source_layout")
        self.prepare()
        job, _ = admit_job(self.user, self.project.id, Job.Operation.CREATION, self.project.revision, "sheet-creation")
        self.assertTrue(run_job(claim_job()))
        job.refresh_from_db()
        self.project.refresh_from_db()
        self.assertEqual(job.result.region_snapshot["generation"]["prompt"], job.input_snapshot["prompt"])
        old = job.result.source_snapshot[0]
        original = self.project.sources.get(id=old["source_id"])
        with original.file.open("rb") as file:
            replacement = validate_and_store_source(self.user, self.project.id, SimpleUploadedFile("replacement.jpg", file.read(), content_type="image/jpeg"), "replacement", "prd-v1", True)
        self.project.refresh_from_db()
        correction, _ = admit_job(self.user, self.project.id, Job.Operation.CORRECTION, self.project.revision, "new-sheet-correction", parent_result_id=job.result_id, target_slot_id=self.slots[0].id, replacement_source_id=replacement.id, correction_action="replace_reference")
        updated = correction.input_snapshot["sources"][0]
        self.assertEqual(updated["source_id"], str(replacement.id))
        self.assertNotEqual(updated["character_sheet"]["id"], old["character_sheet"]["id"])
        self.assertEqual(correction.input_snapshot["sources"][1], job.result.source_snapshot[1])
        self.assertEqual(correction.input_snapshot["image_roles"][0]["role"], "parent")

    def test_source_expiry_removes_dependent_sheet_even_if_sheet_expiry_is_later(self):
        from operations.management.commands.maintenance import expire_assets

        self.configure_character_template(identity_strategy="source_layout")
        self.prepare()
        sheet = self.project.character_sheets.first()
        path = Path(sheet.file.path)
        SourceAsset.objects.filter(pk=sheet.source_id).update(expires_at=timezone.now() - timedelta(seconds=1))
        expire_assets(timezone.now())
        sheet.refresh_from_db()
        self.assertEqual(sheet.status, "expired")
        self.assertFalse(path.exists())

    def test_creation_is_idempotent_and_produces_immutable_media(self):
        self.prepare()
        job, created = admit_job(self.user, self.project.id, Job.Operation.CREATION, self.project.revision, "same-key")
        self.assertTrue(created)
        same, created = admit_job(self.user, self.project.id, Job.Operation.CREATION, self.project.revision, "same-key")
        self.assertFalse(created)
        self.assertEqual(job.id, same.id)
        with self.assertRaises(ApiError) as context:
            admit_job(self.user, self.project.id, Job.Operation.CREATION, self.project.revision + 1, "same-key")
        self.assertEqual(context.exception.code, "idempotency_conflict")
        claimed = claim_job()
        self.assertEqual(claimed.id, job.id)
        self.assertTrue(run_job(claimed))
        job.refresh_from_db()
        self.assertEqual(job.state, Job.State.READY)
        self.assertEqual(job.result.status, ResultVersion.Status.READY)
        self.assertTrue(job.result.synthetic)
        master = job.result.media.get(kind=MediaAsset.Kind.MASTER)
        preview = job.result.media.get(kind=MediaAsset.Kind.PREVIEW)
        self.assertGreaterEqual(max(master.width, master.height), 2048)
        self.assertLessEqual(max(preview.width, preview.height), 768)
        with self.assertRaises(DatabaseError), transaction.atomic():
            ResultVersion.objects.filter(id=job.result_id).update(greeting="changed")

    def test_preview_download_and_paused_template_remain_owner_only(self):
        self.prepare()
        job, _ = admit_job(self.user, self.project.id, Job.Operation.CREATION, self.project.revision, "preview-download")
        run_job(claim_job())
        job.refresh_from_db()
        self.template.status = TemplateVersion.Status.PAUSED
        self.template.save(update_fields=("status",))
        self.client.force_login(self.user)
        project = self.client.get(f"/api/v1/projects/{self.project.id}").json()
        self.assertEqual(project["template"]["name"], self.template.name)
        self.assertEqual(len(project["template"]["slots"]), 2)
        response = self.client.get(f"/api/v1/results/{job.result_id}/preview?download=1")
        self.assertEqual(response.status_code, 200)
        self.assertIn("attachment;", response["Content-Disposition"])
        self.assertEqual(response["Cache-Control"], "private, no-store")
        self.assertTrue(b"".join(response.streaming_content).startswith(b"\xff\xd8"))
        self.assertEqual(self.client.get(f"/api/v1/results/{job.result_id}/master").status_code, 200)
        self.client.force_login(self.other)
        self.assertEqual(self.client.get(f"/api/v1/results/{job.result_id}/preview?download=1").status_code, 404)
        self.client.force_login(self.user)
        with patch("projects.api.timezone.now", return_value=job.result.expires_at + timedelta(seconds=1)):
            self.client.force_login(self.user)
            self.assertEqual(self.client.get(f"/api/v1/results/{job.result_id}/preview?download=1").status_code, 404)

    def test_framed_previews_preserve_pixels_privacy_and_result_history(self):
        self.prepare()
        job, _ = admit_job(self.user, self.project.id, Job.Operation.CREATION, self.project.revision, "framed-preview")
        run_job(claim_job())
        job.refresh_from_db()
        self.client.force_login(self.user)
        original_hashes = list(job.result.media.values_list("sha256", flat=True))
        for name, size in {"square": (2048, 2048), "portrait": (2049, 2732), "story": (2052, 3648)}.items():
            url = f"/api/v1/results/{job.result_id}/preview?download=1&format={name}"
            response = self.client.get(url)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response["Cache-Control"], "private, no-store")
            self.assertIn(f"-{name}.jpg", response["Content-Disposition"])
            with Image.open(io.BytesIO(b"".join(response.streaming_content))) as image:
                self.assertEqual(image.size, size)
            self.client.force_login(self.other)
            self.assertEqual(self.client.get(url).status_code, 404)
            self.client.force_login(self.user)
            with patch("projects.api.timezone.now", return_value=job.result.expires_at + timedelta(seconds=1)):
                self.client.force_login(self.user)
                self.assertEqual(self.client.get(url).status_code, 404)
        self.assertEqual(self.client.get(f"/api/v1/results/{job.result_id}/preview?format=master").status_code, 400)
        self.assertEqual(self.client.get(f"/api/v1/results/{job.result_id}/master").status_code, 200)
        self.assertEqual(self.project.results.count(), 1)
        self.assertEqual(self.project.jobs.count(), 1)
        self.assertEqual(list(job.result.media.values_list("sha256", flat=True)), original_hashes)
        source = Image.new("RGB", (100, 60), "red")
        source.paste("blue", (0, 45, 100, 60))
        content = io.BytesIO()
        source.save(content, "PNG")
        content.seek(0)
        with Image.open(frame_preview(content, (200, 200))) as image:
            self.assertGreater(image.getpixel((52, 72))[0], 220)
            self.assertGreater(image.getpixel((147, 127))[2], 220)
            self.assertGreater(min(image.getpixel((45, 65))), 225)
        preview = job.result.media.get(kind=MediaAsset.Kind.PREVIEW)
        MediaAsset.objects.filter(id=preview.id).update(deleted_at=timezone.now())
        self.assertEqual(self.client.get(f"/api/v1/results/{job.result_id}/preview").status_code, 404)
        self.assertEqual(self.client.get(f"/api/v1/results/{job.result_id}/preview?format=square").status_code, 200)
        MediaAsset.objects.filter(result=job.result, kind=MediaAsset.Kind.MASTER).update(deleted_at=timezone.now())
        self.assertEqual(self.client.get(f"/api/v1/results/{job.result_id}/preview?format=square").status_code, 404)

    def test_editing_greeting_uses_clean_generation_image(self):
        self.prepare()
        job, _ = admit_job(self.user, self.project.id, Job.Operation.CREATION, self.project.revision, "greeting-clean")
        run_job(claim_job())
        job.refresh_from_db()
        self.project.refresh_from_db()
        first = create_greeting(self.user, job.result_id, "Ucapan lama", self.project.revision)
        self.project.refresh_from_db()
        removed = create_greeting(self.user, first.id, "", self.project.revision)
        self.project.refresh_from_db()
        clean = create_greeting(self.user, job.result_id, "", self.project.revision)
        self.assertEqual(removed.media.get(kind=MediaAsset.Kind.MASTER).sha256, clean.media.get(kind=MediaAsset.Kind.MASTER).sha256)

    @override_settings(AI_GATEWAY_MODE="disabled")
    def test_disabled_gateway_does_not_reserve_processing_allowance(self):
        self.prepare()
        with self.assertRaises(ApiError) as context:
            admit_job(self.user, self.project.id, Job.Operation.CREATION, self.project.revision, "disabled-gateway")
        self.assertEqual(context.exception.code, "admission_paused")
        self.assertFalse(self.project.jobs.exists())

    @override_settings(DAILY_BUDGET_IDR=0, ALLOW_UNBOUNDED_TEST_BUDGET=True)
    def test_explicit_unbounded_test_budget_allows_admission(self):
        self.prepare()
        try:
            job, created = admit_job(self.user, self.project.id, Job.Operation.CREATION, self.project.revision, "unbounded-test-budget")
        except ApiError as error:
            self.fail(f"explicit unbounded test budget rejected: {error.code}")
        self.assertTrue(created)
        self.assertEqual(job.state, Job.State.QUEUED)
        self.assertEqual(job.budget_reservation.estimate, 3000)

    def test_9router_generation_sends_ordered_references_and_publishes_real_output(self):
        server, thread, received = self.start_9router()
        try:
            with override_settings(
                AI_GATEWAY_MODE="9router", NINE_ROUTER_BASE_URL=f"http://127.0.0.1:{server.server_port}/v1",
                NINE_ROUTER_API_KEY="test-key", NINE_ROUTER_GENERATION_MODEL="provider/portrait-v1",
                NINE_ROUTER_GENERATION_PATH="/images/generations",
            ):
                self.prepare()
                job, _ = admit_job(self.user, self.project.id, Job.Operation.CREATION, self.project.revision, "real-9router")
                self.assertTrue(run_job(claim_job()))
        finally:
            server.shutdown()
            server.server_close()
            thread.join()
        job.refresh_from_db()
        self.assertFalse(job.result.synthetic)
        self.assertEqual(job.attempts.get().provider_request_id, "req-9router-1")
        self.assertEqual(job.attempts.get().actual_model, "provider/portrait-v1")
        path, headers, payload = received[0]
        self.assertEqual(path, "/v1/images/generations")
        self.assertEqual(headers["Authorization"], "Bearer test-key")
        self.assertEqual(payload["model"], "provider/portrait-v1")
        self.assertEqual(payload["response_format"], "b64_json")
        self.assertEqual(len(payload["images"]), 3)

    def test_9router_correction_sends_parent_master_before_ordered_references(self):
        self.prepare()
        creation, _ = admit_job(self.user, self.project.id, Job.Operation.CREATION, self.project.revision, "9router-correction-parent")
        self.assertTrue(run_job(claim_job()))
        creation.refresh_from_db()
        self.project.refresh_from_db()
        parent_master = creation.result.media.get(kind=MediaAsset.Kind.MASTER)
        server, thread, received = self.start_9router()
        try:
            with override_settings(
                AI_GATEWAY_MODE="9router", NINE_ROUTER_BASE_URL=f"http://127.0.0.1:{server.server_port}/v1",
                NINE_ROUTER_API_KEY="test-key", NINE_ROUTER_GENERATION_MODEL="provider/portrait-v1",
                NINE_ROUTER_GENERATION_PATH="/images/generations",
            ):
                correction, _ = admit_job(
                    self.user, self.project.id, Job.Operation.CORRECTION, self.project.revision, "real-9router-correction",
                    parent_result_id=creation.result_id, target_slot_id=self.slots[0].id, correction_action="enhance",
                )
                self.assertTrue(run_job(claim_job()))
        finally:
            server.shutdown()
            server.server_close()
            thread.join()
        correction.refresh_from_db()
        self.assertFalse(correction.result.synthetic)
        self.assertEqual(correction.result.parent_id, creation.result_id)
        payload = received[0][2]
        first_image = base64.b64decode(payload["images"][0].split(",", 1)[1])
        self.assertEqual(hashlib.sha256(first_image).hexdigest(), parent_master.sha256)
        self.assertEqual(len(payload["images"]), 3)
        self.assertIn("Correct only person 1", payload["prompt"])

    def test_9router_malformed_response_preserves_request_identity_as_uncertain(self):
        server, thread, _ = self.start_9router({"id": "req-malformed-1", "model": "provider/portrait-v1", "data": []})
        try:
            with override_settings(
                AI_GATEWAY_MODE="9router", NINE_ROUTER_BASE_URL=f"http://127.0.0.1:{server.server_port}/v1",
                NINE_ROUTER_API_KEY="test-key", NINE_ROUTER_GENERATION_MODEL="provider/portrait-v1",
                NINE_ROUTER_GENERATION_PATH="/images/generations",
            ):
                self.prepare()
                job, _ = admit_job(self.user, self.project.id, Job.Operation.CREATION, self.project.revision, "9router-malformed")
                self.assertFalse(run_job(claim_job()))
        finally:
            server.shutdown()
            server.server_close()
            thread.join()
        job.refresh_from_db()
        attempt = job.attempts.get()
        self.assertEqual(job.state, Job.State.UNCERTAIN)
        self.assertEqual(attempt.state, attempt.State.UNCERTAIN)
        self.assertEqual(attempt.provider_request_id, "req-malformed-1")

    def test_9router_output_with_wrong_face_count_is_not_published(self):
        image = Image.new("RGB", (2048, 1536), "white")
        content = io.BytesIO()
        image.save(content, "JPEG", quality=95)
        response = {"id": "req-no-faces", "model": "provider/portrait-v1", "data": [{"b64_json": base64.b64encode(content.getvalue()).decode()}]}
        server, thread, _ = self.start_9router(response)
        try:
            with override_settings(
                AI_GATEWAY_MODE="9router", NINE_ROUTER_BASE_URL=f"http://127.0.0.1:{server.server_port}/v1",
                NINE_ROUTER_API_KEY="test-key", NINE_ROUTER_GENERATION_MODEL="provider/portrait-v1",
                NINE_ROUTER_GENERATION_PATH="/images/generations",
            ):
                self.prepare()
                job, _ = admit_job(self.user, self.project.id, Job.Operation.CREATION, self.project.revision, "9router-wrong-face-count")
                self.assertFalse(run_job(claim_job()))
        finally:
            server.shutdown()
            server.server_close()
            thread.join()
        job.refresh_from_db()
        self.assertEqual(job.state, Job.State.FAILED)
        self.assertEqual(job.error_code, "output_face_count_mismatch")
        self.assertFalse(ResultVersion.objects.filter(project=self.project).exists())

    def test_9router_small_output_records_returned_dimensions(self):
        image = Image.new("RGB", (1024, 768), "white")
        content = io.BytesIO()
        image.save(content, "JPEG", quality=95)
        response = {"id": "req-small-output", "model": "provider/portrait-v1", "data": [{"b64_json": base64.b64encode(content.getvalue()).decode()}]}
        server, thread, _ = self.start_9router(response)
        try:
            with override_settings(
                AI_GATEWAY_MODE="9router", NINE_ROUTER_BASE_URL=f"http://127.0.0.1:{server.server_port}/v1",
                NINE_ROUTER_API_KEY="test-key", NINE_ROUTER_GENERATION_MODEL="provider/portrait-v1",
                NINE_ROUTER_GENERATION_PATH="/images/generations",
            ):
                self.prepare()
                job, _ = admit_job(self.user, self.project.id, Job.Operation.CREATION, self.project.revision, "9router-small-output")
                self.assertFalse(run_job(claim_job()))
        finally:
            server.shutdown()
            server.server_close()
            thread.join()
        job.refresh_from_db()
        self.assertEqual(job.error_code, "master_too_small_1024x768")

    def test_9router_provider_output_is_disclosed_before_upscale(self):
        image = Image.open(Path(__file__).resolve().parent.parent / "static/app/assets/lebaran.png").convert("RGB").resize((1448, 1086))
        content = io.BytesIO()
        image.save(content, "JPEG", quality=95)
        response = {"id": "req-upscaled-output", "model": "provider/portrait-v1", "data": [{"b64_json": base64.b64encode(content.getvalue()).decode()}]}
        server, thread, _ = self.start_9router(response)
        try:
            with override_settings(
                AI_GATEWAY_MODE="9router", NINE_ROUTER_BASE_URL=f"http://127.0.0.1:{server.server_port}/v1",
                NINE_ROUTER_API_KEY="test-key", NINE_ROUTER_GENERATION_MODEL="provider/portrait-v1",
                NINE_ROUTER_GENERATION_PATH="/images/generations",
            ):
                self.prepare()
                job, _ = admit_job(self.user, self.project.id, Job.Operation.CREATION, self.project.revision, "9router-upscaled-output")
                self.assertTrue(run_job(claim_job()))
        finally:
            server.shutdown()
            server.server_close()
            thread.join()
        job.refresh_from_db()
        master = job.result.media.get(kind=MediaAsset.Kind.MASTER)
        self.assertEqual((master.width, master.height), (2048, 1536))
        self.assertEqual(job.result.region_snapshot["output"], {"provider_width": 1448, "provider_height": 1086, "width": 2048, "height": 1536, "upscaled": True})
        self.client.force_login(self.user)
        result = self.client.get(f"/api/v1/projects/{self.project.id}").json()["results"][0]
        self.assertEqual(result["output"], {"provider_width": 1448, "provider_height": 1086, "width": 2048, "height": 1536, "upscaled": True})

    def test_expired_result_remains_database_immutable(self):
        self.prepare()
        job, _ = admit_job(self.user, self.project.id, Job.Operation.CREATION, self.project.revision, "immutable-after-expiry")
        run_job(claim_job())
        job.refresh_from_db()
        ResultVersion.objects.filter(id=job.result_id).update(status=ResultVersion.Status.EXPIRED)
        with self.assertRaises(DatabaseError), transaction.atomic():
            ResultVersion.objects.filter(id=job.result_id).update(source_snapshot=[])

    def test_other_owner_cannot_reach_nested_project_objects(self):
        self.prepare()
        job, _ = admit_job(self.user, self.project.id, Job.Operation.CREATION, self.project.revision, "ownership")
        run_job(claim_job())
        job.refresh_from_db()
        self.client.force_login(self.other)
        self.assertEqual(self.client.get(f"/api/v1/results/{job.result_id}/preview").status_code, 404)
        self.assertEqual(self.client.post(f"/api/v1/results/{job.result_id}/orders", {"offer_id": str(self.offer.id)}, content_type="application/json", HTTP_IDEMPOTENCY_KEY="other").status_code, 404)
        self.assertEqual(self.client.delete(f"/api/v1/projects/{self.project.id}", {"confirmation": "DELETE", "password": "strong-password"}, content_type="application/json").status_code, 404)

    def test_greeting_makes_new_version_without_mutating_parent(self):
        self.prepare()
        job, _ = admit_job(self.user, self.project.id, Job.Operation.CREATION, self.project.revision, "creation")
        run_job(claim_job())
        job.refresh_from_db()
        self.project.refresh_from_db()
        child = create_greeting(self.user, job.result_id, "Selalu bersama", self.project.revision)
        job.result.refresh_from_db()
        self.assertEqual(job.result.greeting, "")
        self.assertEqual(child.parent_id, job.result_id)
        self.assertEqual(child.expires_at, job.result.expires_at)
        self.assertEqual(child.greeting, "Selalu bersama")

    def test_correction_rejects_unknown_fields(self):
        self.prepare()
        job, _ = admit_job(self.user, self.project.id, Job.Operation.CREATION, self.project.revision, "correction-parent")
        run_job(claim_job())
        job.refresh_from_db()
        self.project.refresh_from_db()
        self.client.force_login(self.user)
        response = self.client.post(
            f"/api/v1/results/{job.result_id}/corrections",
            {"target_slot_id": str(self.slots[0].id), "operation": "enhance", "expected_revision": self.project.revision, "unexpected": True},
            content_type="application/json",
            HTTP_IDEMPOTENCY_KEY="correction-extra",
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["code"], "invalid_correction")
        self.assertEqual(self.project.jobs.count(), 1)

    def test_correction_rejects_expired_inherited_reference_before_reservation(self):
        self.prepare()
        job, _ = admit_job(self.user, self.project.id, Job.Operation.CREATION, self.project.revision, "correction-expiry-parent")
        run_job(claim_job())
        job.refresh_from_db()
        self.project.refresh_from_db()
        SourceAsset.objects.filter(id=job.result.source_snapshot[0]["source_id"]).update(expires_at=timezone.now() - timedelta(seconds=1))
        with self.assertRaises(ApiError) as context:
            admit_job(
                self.user, self.project.id, Job.Operation.CORRECTION, self.project.revision, "correction-expired",
                parent_result_id=job.result_id, target_slot_id=self.slots[0].id, correction_action="enhance",
            )
        self.assertEqual(context.exception.code, "source_not_ready")
        self.assertEqual(self.project.jobs.count(), 1)

    def test_repeated_corrections_preserve_parent_paid_file_without_allowance_limit(self):
        from .models import Allowance

        self.prepare()
        creation, _ = admit_job(self.user, self.project.id, Job.Operation.CREATION, self.project.revision, "correction-lineage-parent")
        run_job(claim_job())
        creation.refresh_from_db()
        self.project.refresh_from_db()
        parent = creation.result
        Allowance.objects.create(owner=self.user, project=self.project, kind=Allowance.Kind.CORRECTION, policy_version="v1", consumed_at=timezone.now())
        parent_master = parent.media.get(kind=MediaAsset.Kind.MASTER)
        order = Order.objects.create(
            owner=self.user, project=self.project, result=parent, offer=self.offer,
            merchant_reference="MR-CORRECTION-LINEAGE", payment_state=Order.PaymentState.PAID,
            fulfillment_state=Order.FulfillmentState.DOWNLOADABLE, amount_idr=self.offer.price_idr,
            result_id_snapshot=parent.id, result_sha256=parent_master.sha256,
            result_width=parent_master.width, result_height=parent_master.height,
            expires_at=parent.expires_at, paid_at=timezone.now(),
        )
        correction, _ = admit_job(
            self.user, self.project.id, Job.Operation.CORRECTION, self.project.revision, "correction-lineage",
            parent_result_id=parent.id, target_slot_id=self.slots[0].id, correction_action="enhance",
        )
        run_job(claim_job())
        correction.refresh_from_db()
        self.project.refresh_from_db()
        parent.refresh_from_db()
        parent_master.refresh_from_db()
        order.refresh_from_db()
        self.assertEqual(correction.result.parent_id, parent.id)
        self.assertEqual(correction.result.generation_root_id, parent.id)
        self.assertEqual(parent_master.sha256, order.result_sha256)
        self.assertEqual(order.result_id_snapshot, parent.id)
        self.assertIsNone(correction.allowance_id)
        self.client.force_login(self.user)
        response = self.client.patch(
            f"/api/v1/projects/{self.project.id}",
            {"selected_result_id": str(parent.id), "expected_revision": self.project.revision},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["correction_available"])
        self.project.refresh_from_db()
        self.assertEqual(self.project.selected_result_id, parent.id)
        second, created = admit_job(
            self.user, self.project.id, Job.Operation.CORRECTION, self.project.revision, "correction-second",
            parent_result_id=correction.result_id, target_slot_id=self.slots[1].id, correction_action="enhance",
        )
        self.assertTrue(created)
        self.assertTrue(run_job(claim_job()))
        second.refresh_from_db()
        self.assertEqual(second.result.parent_id, correction.result_id)
        self.assertEqual(second.result.generation_root_id, parent.id)
        parent_master.refresh_from_db()
        self.assertEqual(parent_master.sha256, order.result_sha256)

    def test_delete_during_queue_cancels_and_blocks_late_result(self):
        self.prepare()
        job, _ = admit_job(self.user, self.project.id, Job.Operation.CREATION, self.project.revision, "delete-race")
        claimed = claim_job()
        delete_project(self.user, self.project.id)
        self.assertFalse(run_job(claimed))
        job.refresh_from_db()
        self.assertIn(job.state, (Job.State.CANCELLED, Job.State.FAILED))
        self.assertFalse(ResultVersion.objects.filter(project=self.project).exists())

    def test_expired_prepared_lease_requeues_with_budget_reserved(self):
        self.prepare()
        job, _ = admit_job(self.user, self.project.id, Job.Operation.CREATION, self.project.revision, "lease-prepared")
        claim_job()
        Job.objects.filter(id=job.id).update(leased_until=timezone.now() - timedelta(seconds=1))
        reconcile_expired_leases(timezone.now())
        job.refresh_from_db()
        self.assertEqual(job.state, Job.State.QUEUED)
        self.assertEqual(job.budget_reservation.state, job.budget_reservation.State.RESERVED)

    def test_expired_sent_lease_becomes_uncertain(self):
        self.prepare()
        job, _ = admit_job(self.user, self.project.id, Job.Operation.CREATION, self.project.revision, "lease-sent")
        claimed = claim_job()
        claimed.attempts.update(state="sent")
        Job.objects.filter(id=job.id).update(state=Job.State.PROCESSING, leased_until=timezone.now() - timedelta(seconds=1))
        reconcile_expired_leases(timezone.now())
        job.refresh_from_db()
        self.assertEqual(job.state, Job.State.UNCERTAIN)
        self.assertEqual(job.budget_reservation.state, job.budget_reservation.State.RESERVED)

    def test_crash_after_output_write_hides_partial_result_and_cleans_orphan(self):
        self.prepare()
        job, _ = admit_job(self.user, self.project.id, Job.Operation.CREATION, self.project.revision, "crash-after-write")
        claimed = claim_job()
        with patch.object(MediaAsset, "save", side_effect=RuntimeError("forced crash")):
            with self.assertRaises(RuntimeError):
                run_job(claimed)
        job.refresh_from_db()
        self.assertEqual(job.state, Job.State.PROCESSING)
        self.assertEqual(job.attempts.get().state, job.attempts.model.State.SENT)
        self.assertFalse(ResultVersion.objects.filter(project=self.project).exists())
        orphan = next((Path(self.tempdir.name) / "results").rglob("master.jpg"))
        stale = (timezone.now() - timedelta(hours=2)).timestamp()
        os.utime(orphan, (stale, stale))
        cleanup_orphan_media(timezone.now())
        self.assertFalse(orphan.exists())
        Job.objects.filter(id=job.id).update(leased_until=timezone.now() - timedelta(seconds=1))
        reconcile_expired_leases(timezone.now())
        job.refresh_from_db()
        self.assertEqual(job.state, Job.State.UNCERTAIN)
        self.assertEqual(job.budget_reservation.state, job.budget_reservation.State.RESERVED)


@override_settings(AI_GATEWAY_MODE="fake", ADMISSION_ENABLED=True, DAILY_BUDGET_IDR=10000, ALLOW_UNBOUNDED_TEST_BUDGET=False, STORAGE_MIN_FREE_BYTES=0, STORAGE_MAX_USED_PERCENT=100)
class ConcurrentAdmissionTests(TransactionTestCase):
    def setUp(self):
        if connection.vendor != "postgresql":
            self.skipTest("Concurrency proof requires PostgreSQL")
        self.user = User.objects.create_user("race@example.com", "strong-password", email_verified=True)
        offer = Offer.objects.create(version=1, name="Uji", price_idr=19900, active=True)
        template = TemplateVersion.objects.create(slug="race", version=1, name="Race", occasion="Test", people_count=2, description="Test", sample_asset="app/assets/lebaran.png", configuration_hash="c"*64, generation_config={"max_cost_idr":1500}, status=TemplateVersion.Status.DRAFT, evidence_approved=True)
        slots = [FaceSlot.objects.create(template=template, position=index, x=.3*index, y=.3) for index in (1,2)]
        template.status = TemplateVersion.Status.PUBLISHED
        template.save(update_fields=("status",))
        self.project = create_project(self.user, template, offer)
        consent = Consent.objects.create(project=self.project, owner=self.user, text_version="prd-v1", granted=True)
        for index, slot in enumerate(slots):
            source = SourceAsset.objects.create(project=self.project, consent=consent, upload_key=f"race-{index}", content_sha256=str(index)*64, file=f"sources/race-{index}.jpg", original_name="race.jpg", format="JPEG", width=600, height=600, size_bytes=1000, status=SourceAsset.Status.READY, validation_code="fixture", expires_at=timezone.now()+timedelta(days=1))
            SlotAssignment.objects.create(project=self.project, slot=slot, source=source, revision=1)

    def test_twenty_concurrent_requests_admit_one_job(self):
        barrier = threading.Barrier(20)
        outcomes = []

        def submit(index):
            close_old_connections()
            try:
                barrier.wait(timeout=5)
                job, _ = admit_job(self.user, self.project.id, Job.Operation.CREATION, self.project.revision, f"key-{index}")
                outcomes.append(("job", str(job.id)))
            except Exception as error:
                outcomes.append(("error", getattr(error, "code", type(error).__name__)))
            finally:
                connections.close_all()

        threads = [threading.Thread(target=submit, args=(index,)) for index in range(20)]
        for thread in threads: thread.start()
        for thread in threads: thread.join(timeout=10)
        self.assertEqual(Job.objects.filter(project=self.project).count(), 1)
        self.assertEqual(sum(kind == "job" for kind, _ in outcomes), 1)
        self.assertEqual(len(outcomes), 20)

    def test_one_remaining_trial_slot_is_atomic_across_projects(self):
        from .models import Allowance, AllowanceReservation
        from .quota import initialize_trial_allowances
        initialize_trial_allowances(self.user)
        Allowance.objects.filter(owner=self.user, trial_slot__in=(1, 2)).update(consumed_at=timezone.now())
        second = create_project(self.user, self.project.template, self.project.offer)
        consent = Consent.objects.create(project=second, owner=self.user, text_version="prd-v1", granted=True)
        for assignment in self.project.assignments.select_related("source"):
            source = assignment.source
            source.pk = None
            source.project = second
            source.consent = consent
            source.upload_key = f"second-{assignment.slot_id}"
            source.save()
            SlotAssignment.objects.create(project=second, slot=assignment.slot, source=source, revision=1)
        barrier = threading.Barrier(2)
        outcomes = []

        def submit(project):
            close_old_connections()
            try:
                barrier.wait(timeout=5)
                admit_job(self.user, project.id, "creation", project.revision, str(uuid.uuid4()))
                outcomes.append("job")
            except Exception as error:
                outcomes.append(getattr(error, "code", type(error).__name__))
            finally:
                connections.close_all()

        threads = [threading.Thread(target=submit, args=(project,)) for project in (self.project, second)]
        for thread in threads: thread.start()
        for thread in threads: thread.join(timeout=10)
        self.assertCountEqual(outcomes, ["job", "free_pictures_processing"])
        self.assertEqual(AllowanceReservation.objects.filter(allowance__owner=self.user).count(), 1)

    @override_settings(DAILY_BUDGET_IDR=3000)
    def test_global_budget_is_atomic_across_projects(self):
        other = User.objects.create_user("other-race@example.com", "strong-password", email_verified=True)
        other_project = create_project(other, self.project.template, self.project.offer)
        consent = Consent.objects.create(project=other_project, owner=other, text_version="prd-v1", granted=True)
        for index, slot in enumerate(self.project.template.slots.all()):
            source = SourceAsset.objects.create(project=other_project, consent=consent, upload_key=f"other-{index}", content_sha256=f"{index + 2}" * 64, file=f"sources/other-{index}.jpg", original_name="race.jpg", format="JPEG", width=600, height=600, size_bytes=1000, status=SourceAsset.Status.READY, validation_code="fixture", expires_at=timezone.now() + timedelta(days=1))
            SlotAssignment.objects.create(project=other_project, slot=slot, source=source, revision=1)
        barrier = threading.Barrier(2)
        outcomes = []

        def submit(owner, project, key):
            close_old_connections()
            try:
                barrier.wait(timeout=5)
                admit_job(owner, project.id, Job.Operation.CREATION, project.revision, key)
                outcomes.append("job")
            except Exception as error:
                outcomes.append(getattr(error, "code", type(error).__name__))
            finally:
                connections.close_all()

        threads = [threading.Thread(target=submit, args=(self.user, self.project, "first")), threading.Thread(target=submit, args=(other, other_project, "second"))]
        for thread in threads: thread.start()
        for thread in threads: thread.join(timeout=10)
        self.assertEqual(Job.objects.count(), 1)
        self.assertCountEqual(outcomes, ["job", "budget_exhausted"])
