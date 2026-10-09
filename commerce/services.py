import hashlib
import hmac
import json
import uuid
from datetime import timedelta
from decimal import Decimal, InvalidOperation
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.utils import timezone

from momenria.http import ApiError
from operations.models import AuditEvent, OutboxEvent, SupportTicket
from processing.models import IdempotencyRecord, Job
from processing.services import admit_job, canonical_hash
from catalog.models import Offer
from projects.models import MediaAsset, Project, ResultVersion
from projects.services import emit_analytics

from .models import Entitlement, Order, PaymentEvent, Refund


def get_owned_order(owner, order_id, *, lock=False):
    query = Order.objects.select_related("project", "result", "offer", "entitlement").prefetch_related("refunds")
    if lock:
        query = query.select_for_update(of=("self",))
    try:
        return query.get(id=order_id, owner=owner)
    except Order.DoesNotExist as error:
        raise ApiError(404, "not_found", "Pesanannya nggak ketemu. Coba buka lagi dari halaman Pesanan.") from error


def create_generation_order(owner, project_id, data, idempotency_key):
    required = {"offer_id", "expected_revision", "terms_version", "refund_policy_version", "policies_accepted"}
    if set(data) != required or type(data.get("expected_revision")) is not int or data.get("policies_accepted") is not True:
        raise ApiError(400, "invalid_purchase", "Konfirmasi foto, penawaran dan kebijakan sebelum membayar.")
    if not idempotency_key or len(idempotency_key) > 180:
        raise ApiError(400, "idempotency_key_required", "Header Idempotency-Key wajib diisi.")
    request_hash = canonical_hash({"project_id": str(project_id), **data})
    with transaction.atomic():
        get_user_model().objects.select_for_update().get(pk=owner.pk)
        record = IdempotencyRecord.objects.filter(owner=owner, operation="order:generation", key=idempotency_key).first()
        if record:
            if record.request_hash != request_hash:
                raise ApiError(409, "idempotency_conflict", "Kunci pesanan sudah dipakai untuk pembelian berbeda.")
            return Order.objects.select_related("job").get(id=record.response["order_id"]), False
        if not settings.PAYMENT_CHECKOUT_ENABLED or settings.PAYMENT_PROVIDER == "disabled":
            raise ApiError(503, "payment_unavailable", "Pembelian foto baru sedang dijeda. Pesanan lama tetap bisa diperiksa.")
        if settings.AI_GATEWAY_MODE == "fake" and not (settings.APP_ENV == "test" and settings.PAYMENT_PROVIDER == "fake"):
            raise ApiError(409, "synthetic_payment_forbidden", "Hasil simulasi tidak dapat dikenakan pembayaran nyata.")
        if data["terms_version"] != settings.TERMS_VERSION or data["refund_policy_version"] != settings.REFUND_POLICY_VERSION:
            raise ApiError(409, "policy_changed", "Kebijakan berubah. Baca dan konfirmasi versi terbaru sebelum membeli.")
        from momenria.http import uuid_value
        offer = Offer.objects.filter(id=uuid_value(data["offer_id"], "offer_id"), active=True, purchase_unit="generation", price_idr=9900).first()
        if not offer:
            raise ApiError(409, "offer_changed", "Penawaran berubah. Muat ulang harga sebelum membeli.")
        job, _ = admit_job(owner, project_id, Job.Operation.CREATION, data["expected_revision"], idempotency_key, payment_offer=offer)
        order = Order.objects.create(owner=owner, project=job.project, job=job, purpose=Order.Purpose.GENERATION, offer=offer, merchant_reference=f"MR-{uuid.uuid4().hex[:20].upper()}", amount_idr=offer.price_idr, expires_at=timezone.now() + timedelta(minutes=15), terms_version=data["terms_version"], refund_policy_version=data["refund_policy_version"], policies_accepted_at=timezone.now())
        IdempotencyRecord.objects.create(owner=owner, operation="order:generation", key=idempotency_key, request_hash=request_hash, status_code=201, response={"order_id": str(order.id)})
        if settings.PAYMENT_PROVIDER == "fake" and settings.APP_ENV == "test":
            order.payment_state = Order.PaymentState.PENDING
            order.provider_payload = {"kind": "fake_qris", "message": "Pembayaran simulasi, tidak ada uang yang ditagih."}
        else:
            order.payment_state = Order.PaymentState.UNCERTAIN
        order.save(update_fields=("payment_state", "provider_payload", "updated_at"))
        emit_analytics("checkout_started", owner=owner, project=job.project, job=job, order=order)
    return order, True


def create_order(owner, result_id, offer_id, idempotency_key):
    if not idempotency_key:
        raise ApiError(400, "idempotency_key_required", "Header Idempotency-Key wajib diisi.")
    request_hash = canonical_hash({"result_id": str(result_id), "offer_id": str(offer_id)})
    with transaction.atomic():
        record = IdempotencyRecord.objects.filter(owner=owner, operation="order:create", key=idempotency_key).first()
        if record:
            if record.request_hash != request_hash:
                raise ApiError(409, "idempotency_conflict", "Kunci idempotensi sudah dipakai untuk pesanan berbeda.")
            return Order.objects.get(id=record.response["order_id"]), False
        try:
            result = ResultVersion.objects.select_for_update().select_related("project", "project__offer").get(
                id=result_id, project__owner=owner,
            )
        except ResultVersion.DoesNotExist as error:
            raise ApiError(404, "not_found", "Hasilnya nggak ketemu. Coba buka lagi dari Foto saya.") from error
        if result.project.state != Project.State.ACTIVE or result.status != ResultVersion.Status.READY or result.expires_at <= timezone.now() + timedelta(minutes=30):
            raise ApiError(409, "result_unavailable", "Masa simpan hasilnya hampir atau sudah habis, jadi pembayarannya belum bisa dilanjutkan. Hubungi Bantuan, ya.")
        if str(result.project.offer_id) != str(offer_id):
            raise ApiError(409, "offer_mismatch", "Paketnya nggak cocok dengan proyek ini. Cek lagi pesananmu, ya.")
        if result.synthetic:
            raise ApiError(409, "synthetic_result", "Ini hasil simulasi, jadi nggak bisa dibeli, ya.")
        if settings.PAYMENT_PROVIDER == "disabled":
            raise ApiError(503, "payment_unavailable", "Pembayaran belum tersedia. Kamu masih bisa download preview gratis.")
        if settings.PAYMENT_PROVIDER not in {"fake", "midtrans"}:
            raise ApiError(503, "payment_unavailable", "Layanan pembayaran ini belum bisa dipakai. Hubungi Bantuan, ya.")
        try:
            master = result.media.get(kind=MediaAsset.Kind.MASTER, deleted_at__isnull=True)
        except MediaAsset.DoesNotExist as error:
            raise ApiError(409, "master_unavailable", "File resolusi tingginya belum tersedia. Hubungi Bantuan, ya.") from error
        existing = Order.objects.filter(owner=owner, result_id_snapshot=result.id, payment_state__in=(Order.PaymentState.CREATING, Order.PaymentState.PENDING, Order.PaymentState.UNCERTAIN, Order.PaymentState.PAID)).first()
        if existing:
            return existing, False
        now = timezone.now()
        order = Order.objects.create(
            owner=owner, project=result.project, result=result, offer=result.project.offer,
            merchant_reference=f"MR-{uuid.uuid4().hex[:20].upper()}", payment_state=Order.PaymentState.CREATING,
            amount_idr=result.project.offer.price_idr, result_id_snapshot=result.id, result_sha256=master.sha256,
            result_width=master.width, result_height=master.height, expires_at=min(now + timedelta(minutes=15), result.expires_at),
        )
        if settings.PAYMENT_PROVIDER == "fake" and settings.APP_ENV == "test":
            order.payment_state = Order.PaymentState.PENDING
            order.provider_payload = {"kind": "fake_qris", "message": "Ini pembayaran simulasi. Nggak ada uang yang ditagih."}
            order.save(update_fields=("payment_state", "provider_payload", "updated_at"))
        else:
            order.payment_state = Order.PaymentState.UNCERTAIN
            order.provider_payload = {"reason": "merchant_onboarding_required"}
            order.save(update_fields=("payment_state", "provider_payload", "updated_at"))
        response = {"order_id": str(order.id), "status_url": f"/api/v1/orders/{order.id}"}
        IdempotencyRecord.objects.create(owner=owner, operation="order:create", key=idempotency_key, request_hash=request_hash, status_code=201, response=response)
        emit_analytics("checkout_started", owner=owner, project=result.project, result=result, order=order)
        return order, True


def settle_order(order, provider_transaction_id, payload=None, payment_event=None):
    with transaction.atomic():
        order = Order.objects.select_for_update(of=("self",)).select_related("project", "result").get(id=order.id)
        if order.payment_state == Order.PaymentState.PAID:
            if provider_transaction_id and order.provider_transaction_id and provider_transaction_id != order.provider_transaction_id:
                OutboxEvent.objects.get_or_create(topic="payment.possible_duplicate", payload={"order_id": str(order.id), "transaction_id": provider_transaction_id})
                SupportTicket.objects.get_or_create(owner=order.owner, order=order, subject="Kemungkinan pembayaran ganda", defaults={"project": order.project, "message": "Kami menemukan pembayaran kedua untuk pesanan yang sudah lunas. Tim bantuan perlu mengeceknya.", "status": SupportTicket.Status.REFUND_PROGRESS})
            if payment_event:
                PaymentEvent.objects.filter(id=payment_event.id).update(verified=True)
            return order
        if not order.result or not order.project or order.project.state != Project.State.ACTIVE or order.result.status != ResultVersion.Status.READY or order.result.expires_at <= timezone.now():
            order.payment_state = Order.PaymentState.PAID
            order.fulfillment_state = Order.FulfillmentState.UNAVAILABLE
            order.provider_transaction_id = provider_transaction_id
            order.provider_payload = payload or {}
            order.paid_at = timezone.now()
            order.save()
            if payment_event:
                PaymentEvent.objects.filter(id=payment_event.id).update(verified=True)
            OutboxEvent.objects.create(topic="payment.needs_resolution", payload={"order_id": str(order.id)})
            SupportTicket.objects.create(owner=order.owner, project=order.project, order=order, subject="Pembayaran berhasil, tapi filenya belum tersedia", message="Pesananmu perlu ditangani supaya kamu mendapat file atau pengembalian dana.", status=SupportTicket.Status.REFUND_PROGRESS)
            return order
        order.payment_state = Order.PaymentState.PAID
        order.fulfillment_state = Order.FulfillmentState.DOWNLOADABLE
        order.provider_transaction_id = provider_transaction_id
        order.provider_payload = payload or {}
        order.paid_at = timezone.now()
        order.save()
        Entitlement.objects.get_or_create(owner=order.owner, result_id_snapshot=order.result_id_snapshot, defaults={"result": order.result, "order": order})
        if payment_event:
            PaymentEvent.objects.filter(id=payment_event.id).update(verified=True)
        OutboxEvent.objects.create(topic="payment.verified", payload={"order_id": str(order.id), "result_id": str(order.result_id_snapshot)})
        emit_analytics("payment_verified", owner=order.owner, project=order.project, result=order.result, order=order)
        return order


def midtrans_signature_valid(payload):
    required = ("order_id", "status_code", "gross_amount", "signature_key", "transaction_id")
    if any(not isinstance(payload.get(key), str) for key in required):
        return False
    expected = hashlib.sha512((payload["order_id"] + payload["status_code"] + payload["gross_amount"] + settings.PAYMENT_SERVER_KEY).encode()).hexdigest()
    return hmac.compare_digest(expected, payload["signature_key"])


def _midtrans_status(reference):
    if not settings.PAYMENT_SERVER_KEY:
        raise ApiError(503, "payment_unavailable", "Pembayaran belum siap. Coba lagi nanti atau hubungi Bantuan, ya.")
    host = "api.midtrans.com" if settings.PAYMENT_ENV == "production" else "api.sandbox.midtrans.com"
    import base64
    auth = base64.b64encode((settings.PAYMENT_SERVER_KEY + ":").encode()).decode()
    request = Request(f"https://{host}/v2/{reference}/status", headers={"Authorization": f"Basic {auth}", "Accept": "application/json"})
    try:
        with urlopen(request, timeout=10) as response:
            return json.load(response)
    except (HTTPError, URLError, TimeoutError, ValueError) as error:
        raise ApiError(503, "payment_status_unavailable", "Kami belum bisa memastikan status pembayaranmu. Jangan bayar ulang dulu, ya. Cek status atau hubungi Bantuan.") from error


def _validate_settlement(order, status, expected_transaction_id=None):
    try:
        amount_matches = Decimal(status["gross_amount"]) == Decimal(order.amount_idr)
    except (KeyError, InvalidOperation, TypeError, ValueError) as error:
        raise ApiError(400, "payment_mismatch", "Nilai pembayaran tidak cocok.") from error
    identity_matches = status.get("order_id") == order.merchant_reference
    transaction_id = status.get("transaction_id")
    transaction_matches = isinstance(transaction_id, str) and bool(transaction_id) and (not expected_transaction_id or transaction_id == expected_transaction_id)
    qris_matches = status.get("payment_type") == "qris"
    if not all((amount_matches, identity_matches, transaction_matches, qris_matches, status.get("currency") == "IDR")):
        raise ApiError(400, "payment_mismatch", "Identitas atau nilai pembayaran tidak cocok.")
    return status.get("transaction_status") == "settlement" and status.get("status_code") == "200" and status.get("fraud_status") == "accept"


def apply_midtrans_notification(payload):
    if settings.PAYMENT_PROVIDER != "midtrans" or not midtrans_signature_valid(payload):
        raise ApiError(400, "invalid_notification", "Notifikasi pembayaran tidak valid.")
    payload_hash = hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    event_id = payload.get("transaction_id") or payload_hash
    with transaction.atomic():
        event, created = PaymentEvent.objects.get_or_create(
            provider="midtrans", provider_event_id=event_id,
            defaults={"order_reference": payload.get("order_id", ""), "payload_hash": payload_hash, "payload": payload},
        )
    if not created and event.payload_hash != payload_hash:
        raise ApiError(409, "notification_conflict", "Identitas notifikasi dipakai untuk isi berbeda.")
    try:
        order = Order.objects.get(merchant_reference=event.order_reference)
    except Order.DoesNotExist as error:
        raise ApiError(404, "order_unknown", "Pesanan tidak dikenal.") from error
    if not created and event.verified and order.payment_state == Order.PaymentState.PAID:
        return order
    status = _midtrans_status(order.merchant_reference)
    if not _validate_settlement(order, status, payload.get("transaction_id")):
        raise ApiError(409, "payment_not_settled", "Pembayaranmu belum terkonfirmasi. Cek statusnya dulu sebelum bayar lagi, ya.")
    return settle_order(order, status.get("transaction_id", event_id), status, payment_event=event)


def refresh_order(order):
    if settings.PAYMENT_PROVIDER != "midtrans":
        raise ApiError(503, "payment_unavailable", "Status pembayaran belum bisa dicek ulang. Hubungi Bantuan sebelum bayar lagi, ya.")
    status = _midtrans_status(order.merchant_reference)
    if _validate_settlement(order, status):
        return settle_order(order, status.get("transaction_id", ""), status)
    terminal = {"deny": Order.PaymentState.FAILED, "cancel": Order.PaymentState.CANCELLED, "expire": Order.PaymentState.EXPIRED}
    next_state = terminal.get(status.get("transaction_status"))
    if next_state:
        Order.objects.filter(id=order.id).exclude(payment_state=Order.PaymentState.PAID).update(payment_state=next_state, provider_payload=status)
        order.refresh_from_db()
    return order


def request_refund(operator, order_id, reason, idempotency_key):
    if not idempotency_key or len(idempotency_key) > 180:
        raise ApiError(400, "idempotency_key_required", "Header Idempotency-Key wajib diisi.")
    if not isinstance(reason, str):
        raise ApiError(400, "invalid_reason", "Tulis alasan kamu minta pengembalian dana, ya.")
    reason = reason.strip()
    if len(reason) < 10 or len(reason) > 500:
        raise ApiError(400, "invalid_reason", "Ceritakan alasan pengembalian dananya dalam 10–500 karakter, ya.")
    request_hash = canonical_hash({"order_id": str(order_id), "reason": reason})
    with transaction.atomic():
        existing = Refund.objects.filter(idempotency_key=idempotency_key).first()
        if existing:
            if existing.request_hash != request_hash:
                raise ApiError(409, "idempotency_conflict", "Kunci idempotensi sudah dipakai untuk permintaan berbeda.")
            return existing, False
        try:
            order = Order.objects.select_for_update().get(id=order_id, payment_state=Order.PaymentState.PAID)
        except (Order.DoesNotExist, ValueError) as error:
            raise ApiError(404, "not_found", "Pesanan yang sudah dibayar nggak ketemu. Cek lagi di halaman Pesanan, ya.") from error
        refund = Refund.objects.create(order=order, amount_idr=order.amount_idr, reason=reason, idempotency_key=idempotency_key, request_hash=request_hash, requested_by=operator)
        AuditEvent.objects.create(actor=operator, action="refund_requested", object_type="order", object_id=order.id, reason=reason, metadata={"refund_id": str(refund.id), "amount_idr": order.amount_idr})
        OutboxEvent.objects.create(topic="refund.requested", payload={"refund_id": str(refund.id), "order_id": str(order.id)})
        emit_analytics("refund_recorded", owner=order.owner, project=order.project, result=order.result, order=order, dimensions={"refund_id": str(refund.id)})
        return refund, True
