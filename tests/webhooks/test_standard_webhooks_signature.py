import base64
import hashlib
import hmac

import pytest

from apiroute.webhooks import StandardWebhooksSignature, WebhookSignatureError

KEY = b"0123456789abcdef0123456789abcdef"
SECRET = "whsec_" + base64.b64encode(KEY).decode()
BODY = b'{"type": "email.sent"}'
NOW = 1_700_000_000


def headers(key=KEY, msg_id="msg_1", timestamp=NOW, body=BODY, prefix="webhook", extra=""):
    signed = f"{msg_id}.{timestamp}.".encode() + body
    signature = base64.b64encode(hmac.new(key, signed, hashlib.sha256).digest()).decode()
    return {
        f"{prefix}-id": msg_id,
        f"{prefix}-timestamp": str(timestamp),
        f"{prefix}-signature": f"{extra}v1,{signature}",
    }


def standard(secret=SECRET, **kwargs):
    return StandardWebhooksSignature(secret, clock=lambda: NOW, **kwargs)


def test_a_valid_signature_verifies():
    standard().verify(headers(), BODY)


def test_a_secret_without_the_prefix():
    standard(base64.b64encode(KEY).decode()).verify(headers(), BODY)


def test_svix_header_names():
    standard().verify(headers(prefix="svix"), BODY)


def test_one_of_several_signatures_may_match():
    standard().verify(headers(extra="v1,AAAA v2,BBBB "), BODY)


def test_rotated_secrets():
    other = "whsec_" + base64.b64encode(b"x" * 32).decode()
    standard([other, SECRET]).verify(headers(), BODY)


def test_a_tampered_body_fails():
    with pytest.raises(WebhookSignatureError, match="no v1 signature matches"):
        standard().verify(headers(), BODY + b" ")


def test_the_id_is_signed():
    sent = headers()
    sent["webhook-id"] = "msg_2"
    with pytest.raises(WebhookSignatureError):
        standard().verify(sent, BODY)


def test_an_old_timestamp_fails():
    with pytest.raises(WebhookSignatureError, match="outside the tolerance"):
        standard().verify(headers(timestamp=NOW - 400), BODY)


@pytest.mark.parametrize("missing", ["webhook-id", "webhook-timestamp", "webhook-signature"])
def test_missing_headers_fail(missing):
    sent = headers()
    del sent[missing]
    with pytest.raises(WebhookSignatureError, match=f"{missing} header is missing"):
        standard().verify(sent, BODY)


def test_a_timestamp_that_isnt_a_number_fails():
    sent = {**headers(), "webhook-timestamp": "yesterday"}
    with pytest.raises(WebhookSignatureError, match="isn't a Unix time"):
        standard().verify(sent, BODY)


def test_secrets_must_be_base64():
    with pytest.raises(ValueError, match="base64"):
        StandardWebhooksSignature("whsec_not base64!")
    with pytest.raises(ValueError, match="at least one secret"):
        StandardWebhooksSignature([])
