import base64
import hashlib
import hmac
from collections.abc import Iterable, Mapping

import httpx

from apiroute.webhooks.signing_keys import signing_keys
from apiroute.webhooks.webhook_signature_error import WebhookSignatureError


class HmacSignature:
    """A webhook signed with an HMAC of its raw body in one header, as GitHub signs them
    (the defaults: X-Hub-Signature-256: sha256=<hex>), and as many other APIs do with their
    own header, prefix, digest and encoding:

        github = HmacSignature(secret)
        shopify = HmacSignature(
            secret, header="X-Shopify-Hmac-Sha256", prefix="", encoding="base64"
        )

    verify() raises WebhookSignatureError unless the signature matches one of the secrets
    (give several while rotating). The comparison takes constant time. There is no timestamp,
    so this can't detect a replayed request; schemes that sign one (StripeSignature,
    StandardWebhooksSignature) can.
    """

    def __init__(
        self,
        secret: str | bytes | Iterable[str | bytes],
        *,
        header: str = "X-Hub-Signature-256",
        prefix: str = "sha256=",
        digest: str = "sha256",
        encoding: str = "hex",
    ):
        if encoding not in ("hex", "base64"):
            raise ValueError("encoding must be 'hex' or 'base64'")
        hashlib.new(digest)  # an unknown digest fails here, not on the first request
        self._keys = signing_keys(secret)
        self._header = header
        self._prefix = prefix
        self._digest = digest
        self._encoding = encoding

    def verify(self, headers: Mapping[str, str], body: bytes | str) -> None:
        sent = httpx.Headers(headers).get(self._header)
        if sent is None:
            raise WebhookSignatureError(f"the {self._header} header is missing")
        if not sent.startswith(self._prefix):
            raise WebhookSignatureError(
                f"the {self._header} header doesn't start with {self._prefix!r}"
            )
        payload = body.encode() if isinstance(body, str) else body
        signature = sent[len(self._prefix) :].strip()
        if not any(hmac.compare_digest(self._sign(key, payload), signature) for key in self._keys):
            raise WebhookSignatureError("the signature doesn't match")

    def _sign(self, key: bytes, payload: bytes) -> str:
        mac = hmac.new(key, payload, self._digest).digest()
        return mac.hex() if self._encoding == "hex" else base64.b64encode(mac).decode()
