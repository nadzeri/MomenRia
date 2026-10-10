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

    @override_settings(PAYMENT_ENV="sandbox")
    def test_qr_instruction_url_requires_exact_environment_origin(self):
        from .services import validated_qr_url
        good = "https://api.sandbox.midtrans.com/v2/qris/test/qr-code"
        self.assertEqual(validated_qr_url(good), good)
        for url in ("http://api.sandbox.midtrans.com/v2/qris/test/qr-code", "https://api.midtrans.com/v2/qris/test/qr-code", "https://api.sandbox.midtrans.com.evil.example/v2/qris/test/qr-code", "https://user@api.sandbox.midtrans.com/v2/qris/test/qr-code", "https://api.sandbox.midtrans.com/v2/qris/test/qr-code?url=evil", "javascript:alert(1)", None):
            self.assertIsNone(validated_qr_url(url))

    @override_settings(PAYMENT_SERVER_KEY="", PAYMENT_PROVIDER="midtrans")
    def test_missing_server_key_cannot_verify_a_forged_signature(self):
        payload = {"order_id": "MR-UNCONFIGURED", "status_code": "200", "gross_amount": "9900", "transaction_id": "TX-UNCONFIGURED"}
        payload["signature_key"] = hashlib.sha512(b"MR-UNCONFIGURED2009900").hexdigest()
        self.assertFalse(midtrans_signature_valid(payload))


class MidtransSignatureTests(TestCase):
    @override_settings(PAYMENT_PROVIDER="midtrans", PAYMENT_ENV="sandbox")
    def test_pending_lookup_recovers_same_transaction_qr_with_or_without_actions(self):
        from .api import order_json
        from .services import apply_provider_status
        for index, actions in enumerate((None, [{"name": "generate-qr-code-v2", "method": "GET", "url": "https://api.sandbox.midtrans.com/v4/qris/opaque-code/qr-code"}])):
            _, order = self.make_order(f"MR-QR-RECOVER-{index}", state="uncertain")
            _, status = self.notification(order, f"TX-RECOVER-{index}")
            status.update(transaction_status="pending", status_code="201")
            if actions:
                status["actions"] = actions
            with patch("commerce.services._midtrans_status", return_value=status):
                recovered = refresh_order(order)
            expected = actions[0]["url"] if actions else f"https://api.sandbox.midtrans.com/v2/qris/TX-RECOVER-{index}/qr-code"
            self.assertEqual(order_json(recovered)["payment_instructions"].get("qr_url"), expected)
            apply_provider_status(recovered, {**status, "actions": []})
            recovered.refresh_from_db()
            self.assertEqual(order_json(recovered)["payment_instructions"].get("qr_url"), expected)

    def test_late_legacy_settlement_preserves_revocation_and_opens_resolution(self):
        from .services import settle_order
        owner, order = self.make_order("MR-REVOKED-LATE", state="expired")
        grant = Entitlement.objects.create(owner=owner, result=order.result, result_id_snapshot=order.result_id_snapshot, order=order, revoked_at=timezone.now())
        for _ in range(2):
            settle_order(order, "TX-REVOKED-LATE")
        order.refresh_from_db()
        grant.refresh_from_db()
        self.assertEqual(order.payment_state, "paid")
        self.assertEqual(order.fulfillment_state, "unavailable")
        self.assertIsNotNone(grant.revoked_at)
        self.assertEqual(order.refunds.count(), 1)
        self.assertEqual(order.support_tickets.count(), 1)

    @override_settings(PAYMENT_PROVIDER="midtrans", PAYMENT_SERVER_KEY="server-key")
    def test_second_late_legacy_receipt_survives_and_opens_one_duplicate_resolution(self):
        from .services import settle_order
        owner, first = self.make_order("MR-FIRST-PAID")
        settle_order(first, "TX-FIRST-PAID")
        late = Order.objects.create(owner=owner, project=first.project, result=first.result, offer=first.offer, merchant_reference="MR-SECOND-LATE", payment_state="expired", amount_idr=19900, result_id_snapshot=first.result_id_snapshot, result_sha256=first.result_sha256, result_width=2048, result_height=1536, expires_at=first.expires_at)
        payload, status = self.notification(late, "TX-SECOND-LATE")
        with patch("commerce.services._midtrans_status", return_value=status):
            for _ in range(2):
                apply_midtrans_notification(payload)
        late.refresh_from_db()
        self.assertEqual(late.payment_state, "paid")
        self.assertEqual(late.fulfillment_state, "unavailable")
        self.assertEqual(late.provider_transaction_id, "TX-SECOND-LATE")
        self.assertEqual(late.refunds.count(), 1)
        self.assertEqual(late.support_tickets.count(), 1)
        self.assertEqual(Entitlement.objects.filter(owner=owner, revoked_at__isnull=True).count(), 1)
        from .services import record_refund_outcome
        from projects.result_services import authorized_root
        operator = User.objects.create_superuser("duplicate-operator@example.com", "test-password")
        record_refund_outcome(operator, late.refunds.get().id, outcome="succeeded", amount_idr=19900, reference="REF-DUPLICATE-EXTRA", evidence="Verified only the extra payment was refunded", reason="Original funded picture remains available")
        self.assertEqual(authorized_root(first.result, owner).id, first.result_id_snapshot)
        from .services import apply_provider_status
        apply_provider_status(late, {**status, "transaction_status": "refund", "refund_amount": "19900.00", "duplicate_payment_of": "invalid-provider-value"})
        late.refresh_from_db()
        self.assertEqual(late.provider_payload["duplicate_payment_of"], str(first.pk))
        self.assertEqual(authorized_root(first.result, owner).id, first.result_id_snapshot)
        _, original_status = self.notification(first, "TX-FIRST-PAID")
        apply_provider_status(first, {**original_status, "transaction_status": "refund", "refund_amount": "19900.00", "duplicate_payment_of": str(late.pk)})
        with self.assertRaises(ApiError):
            authorized_root(first.result, owner)

    def test_partial_refund_is_visible_and_remaining_refund_cannot_overpay(self):
        from operations.models import AuditEvent
        from .api import order_json
        from .services import apply_provider_status, record_refund_outcome
        _, order = self.make_order("MR-PARTIAL-BEFORE-SETTLEMENT")
        _, status = self.notification(order, "TX-PARTIAL")
        status.update(transaction_status="partial_refund", refund_amount="1990.00")
        for _ in range(2):
            apply_provider_status(order, status)
        order.refresh_from_db()
        self.assertEqual(order.payment_state, "paid")
        self.assertEqual(order.provider_transaction_id, "TX-PARTIAL")
        self.assertEqual(order.support_tickets.count(), 1)
        self.assertEqual(order_json(order)["refund_observed_idr"], 1990)
        self.assertEqual(order_json(order)["refund_remaining_idr"], 17910)
        self.assertEqual(AuditEvent.objects.filter(action="refund.partial_observed", object_id=order.id).count(), 1)
        operator = User.objects.create_superuser("partial-operator@example.com", "test-password")
        refund, _ = request_refund(operator, order.id, "Approved remaining non-delivery refund", "partial-remaining")
        self.assertEqual(refund.amount_idr, 17910)
        values = dict(outcome="succeeded", reference="REF-PARTIAL-REMAINDER", evidence="Verified completed remaining refund with earlier partial report", reason="Confirmed total returned equals the order amount")
        with self.assertRaises(ApiError):
            record_refund_outcome(operator, refund.id, amount_idr=19900, **values)
        record_refund_outcome(operator, refund.id, amount_idr=17910, **values)
        order.refresh_from_db()
        self.assertEqual(order.fulfillment_state, "ended")

    def test_partial_refund_keeps_delivered_access_and_blocks_obsolete_full_request(self):
        from .services import apply_provider_status, settle_order
        _, order = self.make_order("MR-PARTIAL-DELIVERED")
        settle_order(order, "TX-PARTIAL-DELIVERED")
        request_refund(None, order.id, "Approved delivery issue refund", "full-before-partial")
        _, status = self.notification(order, "TX-PARTIAL-DELIVERED")
        status.update(transaction_status="partial_refund", refund_amount="1990.00")
        apply_provider_status(order, status)
        self.assertTrue(Entitlement.objects.filter(order=order, revoked_at__isnull=True).exists())
        with self.assertRaises(ApiError) as error:
            request_refund(None, order.id, "Approved remaining delivery refund", "new-after-partial")
        self.assertEqual(error.exception.code, "refund_reconciliation_required")
        with self.assertRaises(ApiError):
            request_refund(None, order.id, "Approved delivery issue refund", "full-before-partial")
        apply_provider_status(order, {**status, "transaction_status": "refund", "refund_amount": "19900.00"})
        order.refresh_from_db()
        self.assertEqual(order.fulfillment_state, "ended")
        self.assertEqual(order.refunds.filter(state="succeeded").count(), 1)
        self.assertFalse(Entitlement.objects.filter(order=order, revoked_at__isnull=True).exists())

    def test_invalid_partial_refund_amount_leaves_payment_unchanged(self):
        from .services import apply_provider_status
        _, order = self.make_order("MR-PARTIAL-INVALID")
        _, status = self.notification(order, "TX-PARTIAL-INVALID")
        status.update(transaction_status="partial_refund")
        for amount in ("NaN", "-1", "0", "19900", "19901", "1.5", True, None):
            with self.assertRaises(ApiError):
                apply_provider_status(order, {**status, "refund_amount": amount})
        order.refresh_from_db()
        self.assertEqual(order.payment_state, "pending")
        self.assertFalse(order.support_tickets.exists())
        apply_provider_status(order, {**status, "refund_amount": "1990.00", "partial_refund_amount_idr": 19900})
        order.refresh_from_db()
        self.assertEqual(order.provider_payload["partial_refund_amount_idr"], 1990)

    def test_staff_refund_outcome_needs_evidence_and_revokes_once(self):
        from operations.models import AuditEvent
        from .services import record_refund_outcome, settle_order
        user, order = self.make_order("MR-MANUAL-REFUND")
        order = settle_order(order, "TX-MANUAL")
        operator = User.objects.create_superuser("manual-operator@example.com", "test-password")
        refund, _ = request_refund(operator, order.id, "Confirmed delivery failure", "manual-refund")
        values = dict(outcome="succeeded", amount_idr=19900, reference="DASHBOARD-REF-1", evidence="Verified Midtrans dashboard refund report", reason="Confirmed full refund in dashboard")
        for bad in ({**values, "amount_idr": 9900}, {**values, "evidence": ""}, {**values, "amount_idr": True}):
            with self.assertRaises(ApiError):
                record_refund_outcome(operator, refund.id, **bad)
        with self.assertRaises(ApiError):
            record_refund_outcome(user, refund.id, **values)
        self.assertTrue(Entitlement.objects.filter(order=order, revoked_at__isnull=True).exists())
        record_refund_outcome(operator, refund.id, **{**values, "outcome": "uncertain"})
        self.assertTrue(Entitlement.objects.filter(order=order, revoked_at__isnull=True).exists())
        record_refund_outcome(operator, refund.id, **values)
        record_refund_outcome(operator, refund.id, **values)
        order.refresh_from_db()
        self.assertEqual(order.fulfillment_state, "ended")
        self.assertFalse(Entitlement.objects.filter(order=order, revoked_at__isnull=True).exists())
        self.assertEqual(AuditEvent.objects.filter(action="refund.succeeded", actor=operator).count(), 1)
        with self.assertRaises(ApiError):
            record_refund_outcome(operator, refund.id, **{**values, "reference": "ANOTHER-REF"})
        settle_order(order, "TX-MANUAL")
        self.assertFalse(Entitlement.objects.filter(order=order, revoked_at__isnull=True).exists())

    def test_refund_recording_admin_requires_staff_mfa_and_recent_authentication(self):
        from allauth.mfa.models import Authenticator
        from .services import settle_order
        user, order = self.make_order("MR-ADMIN-REFUND")
        order = settle_order(order, "TX-ADMIN")
        operator = User.objects.create_superuser("refund-admin@example.com", "test-password")
        refund, _ = request_refund(operator, order.id, "Confirmed delivery failure", "admin-refund")
        url = f"/admin/commerce/refund/{refund.id}/record/"
        self.client.force_login(user)
        self.assertEqual(self.client.get(url).status_code, 302)
        self.client.force_login(operator)
        self.assertRedirects(self.client.get(url), "/accounts/2fa/", fetch_redirect_response=False)
        Authenticator.objects.create(user=operator, type=Authenticator.Type.TOTP, data={"secret": "test-secret"})
        self.assertEqual(self.client.get(url).status_code, 200)
        values = dict(outcome="succeeded", amount_idr=19900, reference="DASHBOARD-ADMIN-1", evidence="Verified refund report in dashboard", audit_reason="Confirmed complete refund")
        self.assertIn("reauthenticate", self.client.post(url, values)["Location"])
        with patch("allauth.account.internal.flows.reauthentication.did_recently_authenticate", return_value=True):
            response = self.client.post(url, values)
            self.assertEqual(response.status_code, 302, response.context["form"].errors if response.context else "")
        refund.refresh_from_db()
        self.assertEqual(refund.state, "succeeded")

    def make_order(self, reference, state=Order.PaymentState.PENDING):
        user = User.objects.create_user(f"{reference.lower()}@example.com", "strong-password", email_verified=True)
        offer = Offer.objects.create(version=(Offer.objects.order_by("-version").first().version if Offer.objects.exists() else 0) + 1, name="Uji", price_idr=19900, active=True)
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
        self.assertFalse(PaymentEvent.objects.get(order_reference=order.merchant_reference).verified)

    @override_settings(PAYMENT_PROVIDER="midtrans", PAYMENT_SERVER_KEY="server-key")
    @patch("commerce.services._midtrans_status")
    def test_pending_then_settled_notifications_share_transaction_without_conflict(self, status):
        _, order = self.make_order("MR-TRANSITIONS")
        settled_payload, settled_status = self.notification(order, "TX-TRANSITIONS")
        pending_payload = {**settled_payload, "status_code": "201", "transaction_status": "pending"}
        pending_payload["signature_key"] = hashlib.sha512((order.merchant_reference + "201" + "19900.00" + "server-key").encode()).hexdigest()
        status.return_value = {**settled_status, "status_code": "201", "transaction_status": "pending"}
        self.assertEqual(apply_midtrans_notification(pending_payload).payment_state, "pending")
        self.assertFalse(Entitlement.objects.filter(order=order).exists())
        status.return_value = settled_status
        self.assertEqual(apply_midtrans_notification(settled_payload).payment_state, "paid")
        apply_midtrans_notification(settled_payload)
        self.assertEqual(PaymentEvent.objects.filter(order_reference=order.merchant_reference).count(), 2)
        self.assertEqual(Entitlement.objects.filter(order=order).count(), 1)
        status.return_value = {**settled_status, "status_code": "201", "transaction_status": "pending"}
        self.assertEqual(refresh_order(order).payment_state, "paid")

    @override_settings(PAYMENT_PROVIDER="midtrans", PAYMENT_SERVER_KEY="server-key")
    @patch("commerce.services._midtrans_status")
    def test_verified_refund_revokes_access_and_settlement_replay_cannot_restore_it(self, status):
        _, order = self.make_order("MR-REFUND-STATE")
        payload, status.return_value = self.notification(order, "TX-REFUND-STATE")
        apply_midtrans_notification(payload)
        status.return_value = {**status.return_value, "transaction_status": "refund", "refund_amount": "19900.00"}
        refreshed = refresh_order(order)
        self.assertEqual(refreshed.fulfillment_state, "ended")
        self.assertIsNotNone(Entitlement.objects.get(order=order).revoked_at)

        self.assertEqual(order.refunds.get().state, "succeeded")
        status.return_value = {**status.return_value, "transaction_status": "settlement"}
        apply_midtrans_notification(payload)
        self.assertIsNotNone(Entitlement.objects.get(order=order).revoked_at)

    @override_settings(PAYMENT_PROVIDER="midtrans", PAYMENT_SERVER_KEY="server-key")
    def test_signed_malformed_amount_is_rejected_without_server_error(self):
        _, order = self.make_order("MR-MALFORMED-AMOUNT")
        payload, _ = self.notification(order, "TX-MALFORMED")
        payload["gross_amount"] = "invalid"
        payload["signature_key"] = hashlib.sha512((order.merchant_reference + "200invalidserver-key").encode()).hexdigest()
        with self.assertRaises(ApiError) as error:
            apply_midtrans_notification(payload)
        self.assertEqual(error.exception.status, 400)

    @override_settings(PAYMENT_PROVIDER="midtrans", PAYMENT_SERVER_KEY="server-key")
    @patch("commerce.services._midtrans_status")
    def test_malformed_refund_amount_does_not_revoke_access(self, status):
        _, order = self.make_order("MR-MALFORMED-REFUND")
        payload, status.return_value = self.notification(order, "TX-MALFORMED-REFUND")
        apply_midtrans_notification(payload)
        status.return_value = {**status.return_value, "transaction_status": "refund", "refund_amount": None}
        with self.assertRaises(ApiError) as error:
            refresh_order(order)
        self.assertEqual(error.exception.status, 400)
        self.assertIsNone(Entitlement.objects.get(order=order).revoked_at)

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
        self.assertTrue(PaymentEvent.objects.get(order_reference=order.merchant_reference).verified)
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
