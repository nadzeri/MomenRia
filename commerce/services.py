import hashlib
import hmac
import json
import uuid
from datetime import timedelta
from decimal import Decimal, InvalidOperation
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from urllib.parse import quote, urlparse
from http.client import HTTPException

from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.db.models import Q
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from momenria.http import ApiError
from operations.models import AuditEvent, OutboxEvent, SupportTicket
from processing.models import IdempotencyRecord, Job
from processing.services import admit_job, canonical_hash
from catalog.models import Offer
from projects.models import MediaAsset, Project, ResultVersion
from projects.services import emit_analytics

from .models import Entitlement, Order, PaymentEvent, Refund


def get_owned_order(owner, order_id, *, lock=False):
    query = Order.objects.select_related("owner", "project", "result__project", "result__generation_root", "job", "offer", "entitlement").prefetch_related("refunds")
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
        if settings.PAYMENT_PROVIDER == "midtrans" and (not settings.PAYMENT_SERVER_KEY or settings.PAYMENT_QRIS_ACQUIRER not in {"gopay", "airpay shopee"}):
            raise ApiError(503, "payment_unavailable", "QRIS belum diaktifkan untuk layanan ini.")
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
        order.save(update_fields=("payment_state", "provider_payload", "updated_at"))
        emit_analytics("checkout_started", owner=owner, project=job.project, job=job, order=order)
    if settings.PAYMENT_PROVIDER == "midtrans":
        order = start_qris_charge(order)
    return order, True


def create_order(owner, result_id, offer_id, idempotency_key):
    if not idempotency_key or len(idempotency_key) > 180:
        raise ApiError(400, "idempotency_key_required", "Header Idempotency-Key wajib diisi.")
    request_hash = canonical_hash({"result_id": str(result_id), "offer_id": str(offer_id)})
    record = IdempotencyRecord.objects.filter(owner=owner, operation="order:create", key=idempotency_key).first()
    if record:
        if record.request_hash != request_hash:
            raise ApiError(409, "idempotency_conflict", "Kunci sudah dipakai untuk pesanan berbeda.")
        return Order.objects.get(pk=record.response["order_id"], owner=owner), False
    if not ResultVersion.objects.filter(pk=result_id, project__owner=owner).exists():
        raise ApiError(404, "not_found", "Hasilnya tidak ditemukan.")
    raise ApiError(410, "download_purchase_retired", "Download tidak dikenakan biaya lagi. Pembelian berlaku untuk membuat foto baru.")


def settle_order(order, provider_transaction_id, payload=None, payment_event=None):
    with transaction.atomic():
        order = lock_order(order)
        if order.payment_state == Order.PaymentState.PAID:
            if provider_transaction_id and order.provider_transaction_id and provider_transaction_id != order.provider_transaction_id:
                OutboxEvent.objects.get_or_create(topic="payment.possible_duplicate", payload={"order_id": str(order.id), "transaction_id": provider_transaction_id})
                SupportTicket.objects.get_or_create(owner=order.owner, order=order, subject="Kemungkinan pembayaran ganda", defaults={"project": order.project, "message": "Kami menemukan pembayaran kedua untuk pesanan yang sudah lunas. Tim bantuan perlu mengeceknya.", "status": SupportTicket.Status.REFUND_PROGRESS})
            if payment_event:
                PaymentEvent.objects.filter(id=payment_event.id).update(verified=True)
            return order
        if order.purpose == Order.Purpose.GENERATION:
            order.payment_state = Order.PaymentState.PAID
            order.provider_transaction_id = provider_transaction_id
            order.provider_payload = {**order.provider_payload, **(payload or {}), "partial_refund_amount_idr": order.provider_payload.get("partial_refund_amount_idr", 0)}
            order.provider_payload.pop("duplicate_payment_of", None)
            order.paid_at = timezone.now()
            order.save()
            if payment_event:
                PaymentEvent.objects.filter(id=payment_event.id).update(verified=True)
            job = order.job
            from processing.worker import WorkerFailure, _assert_inputs_eligible
            try:
                if job.state != Job.State.AWAITING_PAYMENT or job.budget_reservation.state != "reserved" or job.deletion_epoch != job.project.deletion_epoch:
                    raise WorkerFailure("generation_no_longer_available")
                _assert_inputs_eligible(job)
            except WorkerFailure as error:
                resolve_generation_failure(order, f"Pembuatan tidak dapat dilanjutkan: {error.code}")
                return Order.objects.get(pk=order.pk)
            job.state = Job.State.QUEUED
            job.next_run_at = timezone.now()
            job.save(update_fields=("state", "next_run_at", "updated_at"))
            OutboxEvent.objects.create(topic="job.queued", payload={"job_id": str(job.id), "order_id": str(order.id)})
            emit_analytics("payment_verified", owner=order.owner, project=order.project, job=job, order=order)
            return order
        from projects.result_services import root_access_revoked
        root = order.result.generation_root or order.result if order.result else None
        duplicate = Order.objects.filter(owner=order.owner, result_id_snapshot=order.result_id_snapshot, payment_state=Order.PaymentState.PAID).exclude(pk=order.pk).first()
        if duplicate or not root or not order.project or order.project.state != Project.State.ACTIVE or order.result.status != ResultVersion.Status.READY or order.result.expires_at <= timezone.now() or root.status != ResultVersion.Status.READY or root.expires_at <= timezone.now() or root_access_revoked(root, order.owner):
            order.payment_state = Order.PaymentState.PAID
            order.fulfillment_state = Order.FulfillmentState.UNAVAILABLE
            order.provider_transaction_id = provider_transaction_id
            order.provider_payload = payload or {}
            order.provider_payload.pop("partial_refund_amount_idr", None)
            order.provider_payload.pop("duplicate_payment_of", None)
            if duplicate:
                order.provider_payload["duplicate_payment_of"] = str(duplicate.pk)
            order.paid_at = timezone.now()
            order.save()
            if payment_event:
                PaymentEvent.objects.filter(id=payment_event.id).update(verified=True)
            OutboxEvent.objects.get_or_create(topic="payment.needs_resolution", payload={"order_id": str(order.id)})
            reason = "Pembayaran kedua untuk hasil yang sama perlu diperiksa" if duplicate else "Pembayaran hasil historis tidak dapat dipenuhi tanpa memulihkan akses yang berakhir"
            request_refund(None, order.id, reason, f"legacy-resolution-{order.id}")
            SupportTicket.objects.get_or_create(owner=order.owner, order=order, subject="Pembayaran berhasil, tapi filenya belum tersedia", defaults={"project": order.project, "message": "Pesananmu perlu ditangani supaya kamu mendapat file atau pengembalian dana.", "status": SupportTicket.Status.REFUND_PROGRESS})
            return order
        order.payment_state = Order.PaymentState.PAID
        order.fulfillment_state = Order.FulfillmentState.DOWNLOADABLE
        order.provider_transaction_id = provider_transaction_id
        order.provider_payload = payload or {}
        order.provider_payload.pop("partial_refund_amount_idr", None)
        order.provider_payload.pop("duplicate_payment_of", None)
        order.paid_at = timezone.now()
        order.save()
        Entitlement.objects.get_or_create(owner=order.owner, result_id_snapshot=root.id, defaults={"result": root, "order": order})
        if payment_event:
            PaymentEvent.objects.filter(id=payment_event.id).update(verified=True)
        OutboxEvent.objects.create(topic="payment.verified", payload={"order_id": str(order.id), "result_id": str(order.result_id_snapshot)})
        emit_analytics("payment_verified", owner=order.owner, project=order.project, result=order.result, order=order)
        return order


def lock_order(order):
    get_user_model().objects.select_for_update().get(pk=order.owner_id)
    if order.project_id:
        Project.objects.select_for_update().get(pk=order.project_id)
    if order.job_id:
        Job.objects.select_for_update().get(pk=order.job_id)
    return Order.objects.select_for_update(of=("self",)).select_related("project", "result", "job").get(pk=order.pk)


def resolve_generation_failure(order, reason):
    with transaction.atomic():
        order = lock_order(order)
        if order.payment_state != Order.PaymentState.PAID or order.refunds.filter(state=Refund.State.SUCCEEDED).exists():
            return
        order.fulfillment_state = Order.FulfillmentState.DELIVERY_FAILED
        order.save(update_fields=("fulfillment_state", "updated_at"))
        if order.job.state == Job.State.AWAITING_PAYMENT:
            order.job.state = Job.State.CANCELLED
            order.job.error_code = "paid_generation_unavailable"
            order.job.save(update_fields=("state", "error_code", "updated_at"))
            order.job.budget_reservation.state = "released"
            order.job.budget_reservation.save(update_fields=("state",))
        if not order.refunds.exclude(state=Refund.State.FAILED).exists():
            request_refund(None, order.id, reason, f"generation-failure-{order.id}")
        SupportTicket.objects.get_or_create(owner=order.owner, order=order, subject="Pembuatan foto perlu pengembalian dana", defaults={"project": order.project, "message": reason, "status": SupportTicket.Status.REFUND_PROGRESS})


def midtrans_signature_valid(payload):
    required = ("order_id", "status_code", "gross_amount", "signature_key", "transaction_id")
    if not settings.PAYMENT_SERVER_KEY or any(not isinstance(payload.get(key), str) for key in required):
        return False
    expected = hashlib.sha512((payload["order_id"] + payload["status_code"] + payload["gross_amount"] + settings.PAYMENT_SERVER_KEY).encode()).hexdigest()
    return hmac.compare_digest(expected, payload["signature_key"])


def _midtrans_status(reference):
    return _midtrans_request("GET", f"/v2/{quote(reference, safe='')}/status")


def _midtrans_origin():
    return "https://api.midtrans.com" if settings.PAYMENT_ENV == "production" else "https://api.sandbox.midtrans.com"


def _midtrans_request(method, path, payload=None):
    if not settings.PAYMENT_SERVER_KEY:
        raise ApiError(503, "payment_unavailable", "Pembayaran belum siap. Coba lagi nanti atau hubungi Bantuan, ya.")
    import base64
    auth = base64.b64encode((settings.PAYMENT_SERVER_KEY + ":").encode()).decode()
    request = Request(f"{_midtrans_origin()}{path}", method=method, data=json.dumps(payload).encode() if payload is not None else None, headers={"Authorization": f"Basic {auth}", "Accept": "application/json", "Content-Type": "application/json"})
    try:
        with urlopen(request, timeout=10) as response:
            data = json.loads(response.read(128 * 1024))
            if not isinstance(data, dict):
                raise ValueError("Invalid payment response")
            return data
    except HTTPError as error:
        if method == "GET" and error.code == 404:
            return {"status_code": "404"}
        raise ApiError(503, "payment_status_unavailable", "Status pembayaran belum pasti. Jangan bayar ulang dulu.") from error
    except (URLError, OSError, HTTPException, ValueError) as error:
        raise ApiError(503, "payment_status_unavailable", "Kami belum bisa memastikan status pembayaranmu. Jangan bayar ulang dulu, ya. Cek status atau hubungi Bantuan.") from error


def validated_qr_url(value):
    if not isinstance(value, str):
        return None
    parsed = urlparse(value)
    host = urlparse(_midtrans_origin()).netloc
    if parsed.scheme == "https" and parsed.netloc == host and parsed.path.startswith(("/v2/qris/", "/v4/qris/")) and parsed.path.endswith("/qr-code") and not parsed.query and not parsed.fragment:
        return value
    return None


def start_qris_charge(order, *, retry=False):
    with transaction.atomic():
        order = lock_order(order)
        if order.payment_state not in (Order.PaymentState.CREATING, Order.PaymentState.UNCERTAIN) or order.expires_at <= timezone.now():
            return order
        charge_started_at = parse_datetime(order.provider_payload.get("charge_started_at", ""))
        if charge_started_at and (not retry or order.payment_state == Order.PaymentState.CREATING and charge_started_at > timezone.now() - timedelta(seconds=30)):
            return order
        order.payment_state = Order.PaymentState.CREATING
        order.provider_payload["charge_started_at"] = timezone.now().isoformat()
        order.save(update_fields=("payment_state", "provider_payload", "updated_at"))
    payload = {"payment_type": "qris", "transaction_details": {"order_id": order.merchant_reference, "gross_amount": order.amount_idr}, "item_details": [{"id": str(order.offer_id), "name": "Pembuatan satu foto MomenRia", "quantity": 1, "price": order.amount_idr}], "qris": {"acquirer": settings.PAYMENT_QRIS_ACQUIRER}, "custom_expiry": {"order_time": timezone.localtime(order.created_at).strftime("%Y-%m-%d %H:%M:%S %z"), "expiry_duration": 15, "unit": "minute"}}
    try:
        status = _midtrans_request("POST", "/v2/charge", payload)
        _validate_settlement(order, status)
        return apply_provider_status(order, status)
    except ApiError as error:
        Order.objects.filter(pk=order.pk, payment_state=Order.PaymentState.CREATING).update(payment_state=Order.PaymentState.UNCERTAIN, provider_payload={**order.provider_payload, "message": "Status pembayaran belum pasti. Cek pesanan ini sebelum membayar lagi.", "charge_error": error.code}, updated_at=timezone.now())
        return Order.objects.get(pk=order.pk)


def amount_matches(value, expected):
    try:
        amount = Decimal(value)
        return amount.is_finite() and amount == Decimal(expected)
    except (InvalidOperation, TypeError, ValueError):
        return False


def _validate_settlement(order, status, expected_transaction_id=None):
    amount_valid = amount_matches(status.get("gross_amount"), order.amount_idr)
    identity_matches = status.get("order_id") == order.merchant_reference
    transaction_id = status.get("transaction_id")
    transaction_matches = isinstance(transaction_id, str) and 0 < len(transaction_id) <= 180 and (not expected_transaction_id or transaction_id == expected_transaction_id)
    qris_matches = status.get("payment_type") == "qris"
    if not all((amount_valid, identity_matches, transaction_matches, qris_matches, status.get("currency") == "IDR")):
        raise ApiError(400, "payment_mismatch", "Identitas atau nilai pembayaran tidak cocok.")
    return status.get("transaction_status") == "settlement" and status.get("status_code") == "200" and status.get("fraud_status") == "accept"


def apply_midtrans_notification(payload):
    if settings.PAYMENT_PROVIDER != "midtrans" or not midtrans_signature_valid(payload):
        raise ApiError(400, "invalid_notification", "Notifikasi pembayaran tidak valid.")
    payload_hash = hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    legacy = PaymentEvent.objects.filter(provider="midtrans", provider_event_id=payload["transaction_id"], payload_hash=payload_hash).first()
    with transaction.atomic():
        event, created = (legacy, False) if legacy else PaymentEvent.objects.get_or_create(
            provider="midtrans", provider_event_id=payload_hash,
            defaults={"order_reference": payload["order_id"], "payload_hash": payload_hash, "payload": payload},
        )
    try:
        order = Order.objects.get(merchant_reference=event.order_reference)
    except Order.DoesNotExist as error:
        raise ApiError(404, "order_unknown", "Pesanan tidak dikenal.") from error
    if not created and event.verified and order.payment_state == Order.PaymentState.PAID:
        return order
    if not amount_matches(payload["gross_amount"], order.amount_idr):
        raise ApiError(400, "payment_mismatch", "Nilai pembayaran tidak cocok.")
    return apply_provider_status(order, _midtrans_status(order.merchant_reference), expected_transaction_id=payload["transaction_id"], payment_event=event)


def apply_provider_status(order, status, *, expected_transaction_id=None, payment_event=None):
    settled = _validate_settlement(order, status, expected_transaction_id)
    if settled:
        return settle_order(order, status["transaction_id"], status, payment_event=payment_event)
    state = status.get("transaction_status")
    if state not in {"pending", "deny", "cancel", "expire", "refund", "partial_refund"}:
        raise ApiError(409, "payment_not_settled", "Status pembayaran belum dapat dikonfirmasi. Jangan bayar ulang dulu.")
    with transaction.atomic():
        order = lock_order(order)
        duplicate_of = order.provider_payload.get("duplicate_payment_of")
        order.provider_payload = {**order.provider_payload, **status, "partial_refund_amount_idr": order.provider_payload.get("partial_refund_amount_idr", 0)}
        order.provider_payload.pop("duplicate_payment_of", None)
        if duplicate_of:
            order.provider_payload["duplicate_payment_of"] = duplicate_of
        if state == "partial_refund":
            try:
                refunded = Decimal(status.get("refund_amount"))
                if isinstance(status.get("refund_amount"), bool) or not refunded.is_finite() or refunded != refunded.to_integral_value() or not 0 < refunded < order.amount_idr:
                    raise ValueError
            except (InvalidOperation, TypeError, ValueError) as error:
                raise ApiError(400, "refund_mismatch", "Jumlah pengembalian sebagian tidak valid.") from error
            refunded = max(int(refunded), order.provider_payload.get("partial_refund_amount_idr", 0))
            order.provider_payload["partial_refund_amount_idr"] = refunded
            order.payment_state = Order.PaymentState.PAID
            order.provider_transaction_id = order.provider_transaction_id or status["transaction_id"]
            order.paid_at = order.paid_at or timezone.now()
            if order.job_id and not order.result_id and not order.refunds.filter(state=Refund.State.SUCCEEDED).exists():
                cancel_prepared_job(order.job, "partial_refund_needs_resolution")
                order.fulfillment_state = Order.FulfillmentState.DELIVERY_FAILED
            order.save()
            SupportTicket.objects.get_or_create(owner=order.owner, order=order, subject="Pengembalian sebagian perlu diperiksa", defaults={"project": order.project, "message": "Sebagian dana sudah dikembalikan. Tim bantuan perlu memeriksa sisa pembayaran dan pemenuhan pesanan; jangan bayar ulang.", "status": SupportTicket.Status.REFUND_PROGRESS})
            AuditEvent.objects.get_or_create(action="refund.partial_observed", object_type="order", object_id=order.id, metadata={"amount_idr": refunded, "remaining_idr": order.amount_idr - refunded}, defaults={"reason": "Authenticated Midtrans status confirms a partial refund"})
            OutboxEvent.objects.get_or_create(topic="refund.partial_observed", payload={"order_id": str(order.id), "amount_idr": refunded})
        elif state == "refund":
            if "refund_amount" in status and not amount_matches(status["refund_amount"], order.amount_idr):
                raise ApiError(400, "refund_mismatch", "Jumlah refund tidak cocok.")
            order.payment_state = Order.PaymentState.PAID
            order.provider_transaction_id = order.provider_transaction_id or status["transaction_id"]
            order.paid_at = order.paid_at or timezone.now()
            order.save()
            refund = order.refunds.exclude(state=Refund.State.FAILED).first()
            if not refund:
                refund, _ = request_refund(None, order.id, "Pengembalian dana penuh dikonfirmasi oleh Midtrans", f"provider-refund-{order.id}")
            complete_refund(order, refund, refund.provider_reference or f"MIDTRANS-{status['transaction_id']}")
            AuditEvent.objects.get_or_create(action="refund_verified", object_type="refund", object_id=refund.id, defaults={"reason": "Authenticated Midtrans status confirms full refund", "metadata": {"amount_idr": order.amount_idr}})
        elif order.payment_state != Order.PaymentState.PAID:
            order.payment_state = {"pending": Order.PaymentState.PENDING, "deny": Order.PaymentState.FAILED, "cancel": Order.PaymentState.CANCELLED, "expire": Order.PaymentState.EXPIRED}[state]
            order.provider_transaction_id = status["transaction_id"]
            if state == "pending":
                actions = status.get("actions", [])
                urls = [validated_qr_url(action.get("url")) for action in actions if isinstance(action, dict) and action.get("name") in {"generate-qr-code", "generate-qr-code-v2"} and action.get("method") == "GET"] if isinstance(actions, list) else []
                qr_url = next((url for url in urls if url), None) or validated_qr_url(order.provider_payload.get("qr_url")) or f"{_midtrans_origin()}/v2/qris/{quote(status['transaction_id'], safe='')}/qr-code"
                order.provider_payload.update(kind="qris", qr_url=validated_qr_url(qr_url))
            order.save()
            if state != "pending" and order.job_id:
                cancel_prepared_job(order.job, f"payment_{state}")
            elif order.job_id and order.expires_at <= timezone.now():
                cancel_prepared_job(order.job, "payment_quote_expired")
        else:
            order.save(update_fields=("provider_payload", "updated_at"))
        if payment_event:
            PaymentEvent.objects.filter(pk=payment_event.pk).update(verified=True)
        return order


def cancel_prepared_job(job, reason):
    if job.state in (Job.State.AWAITING_PAYMENT, Job.State.QUEUED):
        job.budget_reservation.state = "released"
        job.budget_reservation.save(update_fields=("state",))
    if job.state in Job.ACTIVE_STATES:
        job.state = Job.State.CANCELLED
        job.error_code = reason
        job.save(update_fields=("state", "error_code", "updated_at"))


def refresh_order(order):
    if settings.APP_ENV == "test" and settings.PAYMENT_PROVIDER == "fake":
        return order
    if settings.PAYMENT_PROVIDER != "midtrans":
        raise ApiError(503, "payment_unavailable", "Status pembayaran belum bisa dicek ulang. Hubungi Bantuan sebelum bayar lagi.")
    status = _midtrans_status(order.merchant_reference)
    if status.get("status_code") == "404" and not order.provider_transaction_id and order.payment_state in (Order.PaymentState.CREATING, Order.PaymentState.UNCERTAIN):
        if order.expires_at > timezone.now():
            return start_qris_charge(order, retry=True)
        with transaction.atomic():
            order = lock_order(order)
            if order.payment_state != Order.PaymentState.PAID:
                order.payment_state = Order.PaymentState.EXPIRED
                order.save(update_fields=("payment_state", "updated_at"))
                if order.job_id:
                    cancel_prepared_job(order.job, "payment_not_created")
        return order
    return apply_provider_status(order, status)


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
            order = lock_order(existing.order)
            existing.refresh_from_db()
            if existing.state != Refund.State.SUCCEEDED and existing.amount_idr != order.amount_idr - order.provider_payload.get("partial_refund_amount_idr", 0):
                raise ApiError(409, "refund_reconciliation_required", "Pengembalian sebagian sudah terjadi. Periksa permintaan lama sebelum mengembalikan sisanya.")
            return existing, False
        try:
            order = Order.objects.get(id=order_id, payment_state=Order.PaymentState.PAID)
        except (Order.DoesNotExist, ValueError) as error:
            raise ApiError(404, "not_found", "Pesanan yang sudah dibayar nggak ketemu. Cek lagi di halaman Pesanan, ya.") from error
        order = lock_order(order)
        remaining = order.amount_idr - order.provider_payload.get("partial_refund_amount_idr", 0)
        existing = order.refunds.exclude(state=Refund.State.FAILED).first()
        if existing:
            if existing.idempotency_key == idempotency_key and existing.request_hash != request_hash:
                raise ApiError(409, "idempotency_conflict", "Kunci idempotensi sudah dipakai untuk permintaan berbeda.")
            if existing.state != Refund.State.SUCCEEDED and existing.amount_idr != remaining:
                raise ApiError(409, "refund_reconciliation_required", "Pengembalian sebagian sudah terjadi. Periksa permintaan lama sebelum mengembalikan sisanya.")
            return existing, False
        try:
            with transaction.atomic():
                refund = Refund.objects.create(order=order, amount_idr=remaining, reason=reason, idempotency_key=idempotency_key, request_hash=request_hash, requested_by=operator)
        except IntegrityError:
            existing = Refund.objects.filter(idempotency_key=idempotency_key).first()
            if not existing:
                raise
            if existing.request_hash != request_hash:
                raise ApiError(409, "idempotency_conflict", "Kunci idempotensi sudah dipakai untuk permintaan berbeda.")
            return existing, False
        AuditEvent.objects.create(actor=operator, action="refund_requested", object_type="order", object_id=order.id, reason=reason, metadata={"refund_id": str(refund.id), "amount_idr": refund.amount_idr})
        OutboxEvent.objects.create(topic="refund.requested", payload={"refund_id": str(refund.id), "order_id": str(order.id)})
        emit_analytics("refund_recorded", owner=order.owner, project=order.project, result=order.result, order=order, dimensions={"refund_id": str(refund.id)})
        return refund, True


def complete_refund(order, refund, reference):
    refund.state = Refund.State.SUCCEEDED
    refund.provider_reference = reference
    refund.save(update_fields=("state", "provider_reference", "updated_at"))
    order.fulfillment_state = Order.FulfillmentState.ENDED
    order.save(update_fields=("fulfillment_state", "updated_at"))
    if order.provider_payload.get("duplicate_payment_of"):
        return
    root_id = order.result.generation_root_id or order.result_id_snapshot if order.result else order.result_id_snapshot
    Entitlement.objects.filter(result_id_snapshot__in=(order.result_id_snapshot, root_id), owner=order.owner, revoked_at__isnull=True).update(revoked_at=timezone.now())
    if order.job_id:
        cancel_prepared_job(order.job, "order_refunded")
    if root_id:
        for job in Job.objects.filter(owner=order.owner, state__in=Job.ACTIVE_STATES).filter(Q(parent_result_id=root_id) | Q(parent_result__generation_root_id=root_id)).select_for_update(of=("self",)):
            cancel_prepared_job(job, "order_refunded")


def record_refund_outcome(operator, refund_id, *, outcome, amount_idr, reference, evidence, reason):
    if not operator.is_active or not operator.is_staff:
        raise ApiError(404, "not_found", "Sumber daya tidak ditemukan.")
    if outcome not in (Refund.State.PROCESSING, Refund.State.UNCERTAIN, Refund.State.FAILED, Refund.State.SUCCEEDED) or type(amount_idr) is not int:
        raise ApiError(400, "invalid_refund", "Status atau jumlah refund tidak valid.")
    if any(not isinstance(value, str) or not minimum <= len(value.strip()) <= maximum for value, minimum, maximum in ((reference, 5, 180), (evidence, 10, 1000), (reason, 10, 500))):
        raise ApiError(400, "refund_evidence_required", "Isi referensi eksternal, bukti terverifikasi dan alasan refund.")
    with transaction.atomic():
        try:
            refund = Refund.objects.select_related("order").get(pk=refund_id)
        except Refund.DoesNotExist as error:
            raise ApiError(404, "not_found", "Refund tidak ditemukan.") from error
        order = lock_order(refund.order)
        refund = Refund.objects.select_for_update().get(pk=refund.pk)
        remaining = order.amount_idr - order.provider_payload.get("partial_refund_amount_idr", 0)
        if order.payment_state != Order.PaymentState.PAID or amount_idr != refund.amount_idr or outcome == Refund.State.SUCCEEDED and amount_idr != remaining:
            raise ApiError(400, "refund_mismatch", "Jumlah harus sesuai permintaan dan sisa dana yang belum dikembalikan.")
        reference = reference.strip()
        if refund.state == Refund.State.SUCCEEDED:
            if outcome == Refund.State.SUCCEEDED and refund.provider_reference == reference:
                return refund
            raise ApiError(409, "refund_already_completed", "Refund ini sudah selesai; rekaman tidak boleh diubah.")
        if Refund.objects.exclude(pk=refund.pk).filter(provider_reference=reference).exists():
            raise ApiError(409, "refund_reference_used", "Referensi ini sudah dipakai refund lain.")
        try:
            with transaction.atomic():
                if outcome == Refund.State.SUCCEEDED:
                    complete_refund(order, refund, reference)
                else:
                    refund.state, refund.provider_reference = outcome, reference
                    refund.save(update_fields=("state", "provider_reference", "updated_at"))
        except IntegrityError as error:
            raise ApiError(409, "refund_reference_used", "Referensi ini sudah dipakai refund lain.") from error
        AuditEvent.objects.create(actor=operator, action=f"refund.{outcome}", object_type="refund", object_id=refund.id, reason=reason.strip(), metadata={"amount_idr": amount_idr, "reference": reference, "evidence": evidence.strip()})
        OutboxEvent.objects.create(topic=f"refund.{outcome}", payload={"refund_id": str(refund.id), "order_id": str(order.id)})
        return refund
