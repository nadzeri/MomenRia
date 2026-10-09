import hashlib
import hmac
import ipaddress
import socket
from datetime import datetime, timezone as datetime_timezone

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from momenria.http import ApiError

from .models import RateLimitBucket


def _hash(value):
    return hmac.new(settings.SECRET_KEY.encode(), value.encode(), hashlib.sha256).hexdigest()


def _consume(action, identifier, limit, seconds):
    now = timezone.now()
    epoch = int(now.timestamp())
    start = datetime.fromtimestamp(epoch - epoch % seconds, tz=datetime_timezone.utc)
    with transaction.atomic():
        bucket, _ = RateLimitBucket.objects.select_for_update().get_or_create(action=action, identifier_hash=_hash(identifier), window_start=start)
        if bucket.count >= limit:
            raise ApiError(429, "rate_limited", "Terlalu banyak percobaan dalam waktu singkat. Tunggu sebentar, lalu coba lagi, ya.", {"retry_after_seconds": seconds - (epoch % seconds)})
        bucket.count += 1
        bucket.save(update_fields=("count",))


def client_network(request):
    remote = request.META.get("REMOTE_ADDR", "unknown")
    header = request.META.get("HTTP_X_MOMENRIA_CLIENT_IP", "")
    if not settings.TRUSTED_PROXY_HOST or not header:
        return remote
    try:
        client = ipaddress.ip_address(header)
        peer = ipaddress.ip_address(remote)
        trusted = {ipaddress.ip_address(address[4][0]) for address in socket.getaddrinfo(settings.TRUSTED_PROXY_HOST, None, type=socket.SOCK_STREAM)}
    except (OSError, ValueError):
        return remote
    return str(client) if peer in trusted else remote


def check_rate_limit(request, action, *, limit, seconds):
    network = client_network(request)
    _consume(action, f"network:{network}", limit, seconds)
    if request.user.is_authenticated:
        _consume(action, f"owner:{request.user.id}", limit, seconds)
