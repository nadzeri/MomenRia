from django.conf import settings
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt

from momenria.http import ApiError, api_view, body_json, operator_api_view, public_api_view, uuid_value
from operations.rate_limit import check_rate_limit
from projects.result_services import authorized_root

from .services import apply_midtrans_notification, create_generation_order, create_order, get_owned_order, refresh_order, request_refund, settle_order, validated_qr_url


def order_json(order):
    downloadable = False
    if order.fulfillment_state == order.FulfillmentState.DOWNLOADABLE and order.result:
        try:
            authorized_root(order.result, order.owner)
            downloadable = order.result.media.filter(kind="master", deleted_at__isnull=True, expires_at__gt=timezone.now()).exists()
        except ApiError:
            pass
    instructions = {key: order.provider_payload[key] for key in ("kind", "message") if key in order.provider_payload}
    qr_url = validated_qr_url(order.provider_payload.get("qr_url"))
    if qr_url and order.payment_state in (order.PaymentState.CREATING, order.PaymentState.PENDING, order.PaymentState.UNCERTAIN) and order.expires_at > timezone.now() and (not order.job_id or order.job.state == "awaiting_payment"):
        instructions["qr_url"] = qr_url
    refunds = list(order.refunds.order_by("created_at"))
    returned = order.amount_idr if any(item.state == "succeeded" for item in refunds) else order.provider_payload.get("partial_refund_amount_idr", 0)
    return {
        "id": str(order.id), "merchant_reference": order.merchant_reference,
        "result_id": str(order.result_id_snapshot) if order.result_id_snapshot else None,
        "job_id": str(order.job_id) if order.job_id else None, "purpose": order.purpose,
        "job_state": order.job.state if order.job_id else None, "project_id": str(order.project_id) if order.project_id else None,
        "amount": order.amount_idr, "currency": order.currency,
        "refund_observed_idr": returned, "refund_remaining_idr": order.amount_idr - returned,
        "payment_state": order.payment_state, "fulfillment_state": order.fulfillment_state,
        "payment_instructions": instructions, "expires_at": order.expires_at.isoformat(),
        "download_url": f"/api/v1/results/{order.result_id_snapshot}/master" if downloadable else None,
        "refunds": [{"id": str(item.id), "state": item.state, "amount_idr": item.amount_idr} for item in refunds],
    }


@api_view("POST")
def orders(request, result_id):
    check_rate_limit(request, "order", limit=20, seconds=3600)
    data = body_json(request)
    if set(data) != {"offer_id"}:
        raise ApiError(400, "invalid_fields", "Referensi penawaran wajib diisi.")
    order, created = create_order(request.user, result_id, uuid_value(data["offer_id"], "offer_id"), request.headers.get("Idempotency-Key", ""))
    return JsonResponse(order_json(order), status=201 if created else 200)


@api_view("POST", verified=True)
def generation_orders(request, project_id):
    check_rate_limit(request, "order", limit=20, seconds=3600)
    order, created = create_generation_order(request.user, project_id, body_json(request), request.headers.get("Idempotency-Key", ""))
    return JsonResponse(order_json(order), status=201 if created else 200)


@api_view("GET")
def order_list(request):
    rows = request.user.orders.select_related("owner", "entitlement", "job", "project", "result__project", "result__generation_root").prefetch_related("refunds").order_by("-created_at")[:50]
    return JsonResponse({"items": [order_json(order) for order in rows]})


@api_view("GET")
def order_detail(request, order_id):
    return JsonResponse(order_json(get_owned_order(request.user, order_id)))


@api_view("POST")
def order_refresh(request, order_id):
    check_rate_limit(request, "payment_refresh", limit=12, seconds=300)
    return JsonResponse(order_json(refresh_order(get_owned_order(request.user, order_id))))


@api_view("POST")
def fake_settle(request, order_id):
    if settings.APP_ENV != "test" or settings.PAYMENT_PROVIDER != "fake":
        raise ApiError(404, "not_found", "Pesanannya nggak ketemu. Coba buka lagi dari halaman Pesanan.")
    order = get_owned_order(request.user, order_id)
    return JsonResponse(order_json(settle_order(order, f"FAKE-{order.id}", {"test": True})))


@csrf_exempt
@public_api_view("POST")
def webhook(request):
    order = apply_midtrans_notification(body_json(request))
    return JsonResponse({"accepted": True, "order_id": str(order.id)})


@operator_api_view("POST", recent_auth=True)
def refund(request, order_id):
    data = body_json(request)
    if set(data) != {"reason"}:
        raise ApiError(400, "invalid_fields", "Data pengembalian dana tidak valid.")
    item, created = request_refund(request.user, order_id, data.get("reason", ""), request.headers.get("Idempotency-Key", ""))
    return JsonResponse({"id": str(item.id), "order_id": str(item.order_id), "state": item.state, "amount_idr": item.amount_idr}, status=201 if created else 200)
