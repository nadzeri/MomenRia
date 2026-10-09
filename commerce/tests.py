import hashlib
import json
from datetime import timedelta
from unittest.mock import patch

from django.db import IntegrityError, transaction
from django.test import TestCase, override_settings
from django.utils import timezone

from accounts.models import User
from catalog.models import Offer, TemplateVersion
from projects.models import Project, ResultVersion

from momenria.http import ApiError
from operations.models import SupportTicket

from .models import Entitlement, Order, PaymentEvent, Refund
from .services import apply_midtrans_notification, midtrans_signature_valid, refresh_order, request_refund


class GenerationOrderModelTests(TestCase):
    def test_downloadable_order_requires_dimensions(self):
        from accounts.models import User
        from catalog.models import Offer
        from uuid import uuid4
        owner = User.objects.create_user("dimensions@example.com", "strong-password")
        offer = Offer.objects.create(version=1, name="Test", price_idr=9900)
        with self.assertRaises(IntegrityError), transaction.atomic():
            Order.objects.create(owner=owner, offer=offer, merchant_reference="MR-NO-DIMENSIONS", amount_idr=9900, result_id_snapshot=uuid4(), result_sha256="a" * 64, fulfillment_state="downloadable", expires_at=timezone.now())


class MidtransSignatureTests(TestCase):
    def make_order(self, reference, state=Order.PaymentState.PENDING):
        user = User.objects.create_user(f"{reference.lower()}@example.com", "strong-password", email_verified=True)
        offer = Offer.objects.create(version=Offer.objects.count() + 1, name="Uji", price_idr=19900, active=True)
        template = TemplateVersion.objects.create(slug=reference.lower(), version=1, name="Pay", occasion="Test", people_count=2, description="Test", sample_asset="sample.jpg", configuration_hash="d" * 64, generation_config={"model": "test"}, evidence_approved=True)
        project = Project.objects.create(owner=user, template=template, offer=offer, state=Project.State.ACTIVE)
        result = ResultVersion.objects.create(project=project, source_snapshot={}, region_snapshot={}, configuration_hash="d" * 64, kind=ResultVersion.Kind.CREATION, number=1, status=ResultVersion.Status.READY, expires_at=timezone.now() + timedelta(days=1))
        order = Order.objects.create(owner=user, project=project, result=result, offer=offer, merchant_reference=reference, payment_state=state, amount_idr=19900, result_id_snapshot=result.id, result_sha256="e" * 64, result_width=2048, result_height=1536, expires_at=timezone.now() + timedelta(minutes=15))
        return user, order

    def notification(self, order, transaction_id):
        payload = {"order_id": order.merchant_reference, "status_code": "200", "gross_amount": "19900.00", "transaction_id": transaction_id}
        payload["signature_key"] = hashlib.sha512((payload["order_id"] + payload["status_code"] + payload["gross_amount"] + "server-key").encode()).hexdigest()
        status = {"order_id": order.merchant_reference, "payment_type": "qris", "transaction_status": "settlement", "status_code": "200", "currency": "IDR", "fraud_status": "accept", "gross_amount": "19900.00", "transaction_id": transaction_id}
        return payload, status

    @override_settings(PAYMENT_SERVER_KEY="server-key")
    def test_signature_uses_original_amount_string(self):
        payload = {"order_id":"MR-1", "status_code":"200", "gross_amount":"19900.00", "transaction_id": "TX-1"}
        payload["signature_key"] = hashlib.sha512((payload["order_id"] + payload["status_code"] + payload["gross_amount"] + "server-key").encode()).hexdigest()
        self.assertTrue(midtrans_signature_valid(payload))
        payload["gross_amount"] = "19900"
        self.assertFalse(midtrans_signature_valid(payload))

    @override_settings(PAYMENT_PROVIDER="midtrans", PAYMENT_SERVER_KEY="server-key")
    @patch("commerce.services._midtrans_status")
    def test_unverified_duplicate_retries_provider_verification(self, status):
        _, order = self.make_order("MR-RETRY")
        payload, response = self.notification(order, "TX-1")
        payload_hash = hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
        PaymentEvent.objects.create(provider="midtrans", provider_event_id="TX-1", order_reference=order.merchant_reference, payload_hash=payload_hash, payload=payload)
        status.return_value = response
        settled = apply_midtrans_notification(payload)
        self.assertEqual(settled.payment_state, Order.PaymentState.PAID)
        self.assertTrue(Entitlement.objects.filter(order=order).exists())
        self.assertTrue(PaymentEvent.objects.get(provider_event_id="TX-1").verified)

    @override_settings(PAYMENT_PROVIDER="midtrans", PAYMENT_SERVER_KEY="server-key")
    @patch("commerce.services._midtrans_status")
    def test_receipt_and_entitlement_commit_atomically(self, status):
        _, order = self.make_order("MR-ATOMIC")
        payload, status.return_value = self.notification(order, "TX-ATOMIC")
        with patch("commerce.services.Entitlement.objects.get_or_create", side_effect=IntegrityError("forced")):
            with self.assertRaises(IntegrityError):
                apply_midtrans_notification(payload)
        order.refresh_from_db()
        self.assertEqual(order.payment_state, Order.PaymentState.PENDING)
        self.assertFalse(PaymentEvent.objects.get(provider_event_id="TX-ATOMIC").verified)

    @override_settings(PAYMENT_PROVIDER="midtrans", PAYMENT_SERVER_KEY="server-key")
    @patch("commerce.services._midtrans_status")
    def test_missing_verified_identity_fields_grant_no_download(self, status):
        for index, field in enumerate(("currency", "fraud_status", "notification_transaction_id", "gross_amount_none"), 1):
            with self.subTest(field=field):
                _, order = self.make_order(f"MR-MISSING-{index}")
                payload, provider_status = self.notification(order, f"TX-MISSING-{index}")
                if field == "notification_transaction_id":
                    payload.pop("transaction_id")
                elif field == "gross_amount_none":
                    provider_status["gross_amount"] = None
                else:
                    provider_status.pop(field)
                status.return_value = provider_status
                with self.assertRaises(ApiError):
                    apply_midtrans_notification(payload)
                order.refresh_from_db()
                self.assertEqual(order.payment_state, Order.PaymentState.PENDING)
                self.assertFalse(Entitlement.objects.filter(order=order).exists())

    @override_settings(PAYMENT_PROVIDER="midtrans", PAYMENT_SERVER_KEY="server-key")
    @patch("commerce.services._midtrans_status")
    def test_authenticated_refresh_settles_provider_transaction(self, status):
        _, order = self.make_order("MR-REFRESH")
        _, status.return_value = self.notification(order, "TX-REFRESH")
        settled = refresh_order(order)
        self.assertEqual(settled.payment_state, Order.PaymentState.PAID)
        self.assertEqual(settled.provider_transaction_id, "TX-REFRESH")
        self.assertTrue(Entitlement.objects.filter(order=order).exists())

    @override_settings(PAYMENT_PROVIDER="midtrans", PAYMENT_SERVER_KEY="server-key")
    @patch("commerce.services._midtrans_status")
    def test_late_settlement_for_deleted_result_records_resolution_without_entitlement(self, status):
        _, order = self.make_order("MR-LATE-DELETED", Order.PaymentState.EXPIRED)
        payload, status.return_value = self.notification(order, "TX-LATE-DELETED")
        Project.objects.filter(id=order.project_id).update(state=Project.State.DELETED)
        ResultVersion.objects.filter(id=order.result_id).update(status=ResultVersion.Status.DELETED)
        settled = apply_midtrans_notification(payload)
        self.assertEqual(settled.payment_state, Order.PaymentState.PAID)
        self.assertEqual(settled.fulfillment_state, Order.FulfillmentState.UNAVAILABLE)
        self.assertFalse(Entitlement.objects.filter(order=order).exists())
        self.assertTrue(PaymentEvent.objects.get(provider_event_id="TX-LATE-DELETED").verified)
        self.assertTrue(SupportTicket.objects.filter(order=order).exists())

    @override_settings(PAYMENT_PROVIDER="midtrans", PAYMENT_SERVER_KEY="server-key")
    @patch("commerce.services._midtrans_status")
    def test_late_settlement_for_live_result_fulfills_once(self, status):
        _, order = self.make_order("MR-LATE-LIVE", Order.PaymentState.EXPIRED)
        payload, status.return_value = self.notification(order, "TX-LATE-LIVE")
        first = apply_midtrans_notification(payload)
        second = apply_midtrans_notification(payload)
        self.assertEqual(first.payment_state, Order.PaymentState.PAID)
        self.assertEqual(first.fulfillment_state, Order.FulfillmentState.DOWNLOADABLE)
        self.assertEqual(second.id, first.id)
        self.assertEqual(Entitlement.objects.filter(order=order).count(), 1)

    def test_refund_request_is_idempotent_and_conflict_safe(self):
        _, order = self.make_order("MR-REFUND", Order.PaymentState.PAID)
        operator = User.objects.create_superuser("operator@example.com", "strong-password")
        first, created = request_refund(operator, order.id, "Berkas berbayar tidak tersedia", "refund-key")
        second, created_again = request_refund(operator, order.id, "Berkas berbayar tidak tersedia", "refund-key")
        self.assertTrue(created)
        self.assertFalse(created_again)
        self.assertEqual(first.id, second.id)
        self.assertEqual(Refund.objects.count(), 1)
        with self.assertRaises(ApiError):
            request_refund(operator, order.id, "Alasan berbeda untuk pesanan sama", "refund-key")

    def test_refund_rejects_non_string_reason(self):
        _, order = self.make_order("MR-REFUND-SCHEMA", Order.PaymentState.PAID)
        operator = User.objects.create_superuser("refund-schema@example.com", "strong-password")
        with self.assertRaises(ApiError) as context:
            request_refund(operator, order.id, {"reason": "Berkas tidak tersedia"}, "refund-schema-key")
        self.assertEqual(context.exception.code, "invalid_reason")
        self.assertFalse(Refund.objects.filter(order=order).exists())
