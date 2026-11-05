import base64
import binascii
import hashlib
import hmac
import time
from collections.abc import Callable, Iterable, Mapping

import httpx

from apiroute.webhooks.webhook_signature_error import WebhookSignatureError


class StandardWebhooksSignature:
    """A webhook signed by the Standard Webhooks spec (standardwebhooks.com), as Svix, Resend,
    Clerk, OpenAI and others send them: webhook-id, webhook-timestamp and webhook-signature
    headers, the last holding "v1,<base64>" entries, each the HMAC-SHA256 of
    "<id>.<timestamp>.<raw body>" keyed with the secret's base64 part (after "whsec_").

    verify() raises WebhookSignatureError unless an entry matches one of the secrets and the
    timestamp is within `tolerance` seconds of now. The svix-* header names are accepted too.
    """

    def __init__(
        self,
        secret: str | Iterable[str],
        *,
        tolerance: float = 300,
        clock: Callable[[], float] = time.time,
    ):
        secrets = [secret] if isinstance(secret, str) else list(secret)
        if not secrets:
            raise ValueError("a webhook signature needs at least one secret")
        self._keys = [_key(s) for s in secrets]
        self._tolerance = tolerance
        self._clock = clock

    def verify(self, headers: Mapping[str, str], body: bytes | str) -> None:
        found = httpx.Headers(headers)
        message_id = _header(found, "id")
        timestamp = _header(found, "timestamp")
        sent = _header(found, "signature")
        if not timestamp.isdigit():
            raise WebhookSignatureError("the webhook-timestamp header isn't a Unix time")
        payload = body.encode() if isinstance(body, str) else body
        signed = f"{message_id}.{timestamp}.".encode() + payload
        expected = [
            base64.b64encode(hmac.new(key, signed, hashlib.sha256).digest()).decode()
            for key in self._keys
        ]
        signatures = [entry.partition(",")[2] for entry in sent.split() if entry.startswith("v1,")]
        if not any(hmac.compare_digest(e, s) for e in expected for s in signatures):
            raise WebhookSignatureError("no v1 signature matches")
        if abs(self._clock() - int(timestamp)) > self._tolerance:
            raise WebhookSignatureError("the signature's timestamp is outside the tolerance")


def _header(headers: httpx.Headers, name: str) -> str:
    value = headers.get(f"webhook-{name}") or headers.get(f"svix-{name}")
    if value is None:
        raise WebhookSignatureError(f"the webhook-{name} header is missing")
    return value


def _key(secret: str) -> bytes:
    try:
        return base64.b64decode(secret.removeprefix("whsec_"), validate=True)
    except (binascii.Error, ValueError):
        raise ValueError("a Standard Webhooks secret is base64, optionally after whsec_") from None
