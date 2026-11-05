import hashlib
import hmac
import time
from collections.abc import Callable, Iterable, Mapping

import httpx

from apiroute.webhooks.signing_keys import signing_keys
from apiroute.webhooks.webhook_signature_error import WebhookSignatureError


class StripeSignature:
    """A webhook signed as Stripe signs them: Stripe-Signature: t=<unix time>,v1=<hex>, the
    HMAC-SHA256 of "<t>.<raw body>" with the endpoint's signing secret (whsec_...).

    verify() raises WebhookSignatureError unless a v1 signature matches one of the secrets and
    t is within `tolerance` seconds of now, which stops a captured request being replayed later.
    """

    def __init__(
        self,
        secret: str | bytes | Iterable[str | bytes],
        *,
        tolerance: float = 300,
        clock: Callable[[], float] = time.time,
    ):
        self._keys = signing_keys(secret)
        self._tolerance = tolerance
        self._clock = clock

    def verify(self, headers: Mapping[str, str], body: bytes | str) -> None:
        sent = httpx.Headers(headers).get("Stripe-Signature")
        if sent is None:
            raise WebhookSignatureError("the Stripe-Signature header is missing")
        timestamp, signatures = _parse(sent)
        payload = body.encode() if isinstance(body, str) else body
        signed = timestamp.encode() + b"." + payload
        expected = [hmac.new(key, signed, hashlib.sha256).hexdigest() for key in self._keys]
        if not any(hmac.compare_digest(e, s) for e in expected for s in signatures):
            raise WebhookSignatureError("no v1 signature matches")
        if abs(self._clock() - int(timestamp)) > self._tolerance:
            raise WebhookSignatureError("the signature's timestamp is outside the tolerance")


def _parse(header: str) -> tuple[str, list[str]]:
    timestamp, signatures = None, []
    for item in header.split(","):
        key, _, value = item.strip().partition("=")
        if key == "t":
            timestamp = value
        elif key == "v1":
            signatures.append(value)
    if timestamp is None or not timestamp.isdigit():
        raise WebhookSignatureError("the Stripe-Signature header has no timestamp")
    if not signatures:
        raise WebhookSignatureError("the Stripe-Signature header has no v1 signature")
    return timestamp, signatures
