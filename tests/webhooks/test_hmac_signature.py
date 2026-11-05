import base64
import hashlib
import hmac

import pytest

from apiroute.webhooks import HmacSignature, WebhookSignatureError

BODY = b'{"action": "opened"}'


def github(secret=b"s3cret", body=BODY):
    return "sha256=" + hmac.new(secret, body, hashlib.sha256).hexdigest()


def test_a_github_signature_verifies():
    HmacSignature("s3cret").verify({"X-Hub-Signature-256": github()}, BODY)


def test_header_names_are_case_insensitive_and_str_bodies_are_encoded():
    HmacSignature("s3cret").verify({"x-hub-signature-256": github()}, BODY.decode())


def test_a_tampered_body_fails():
    with pytest.raises(WebhookSignatureError, match="doesn't match"):
        HmacSignature("s3cret").verify({"X-Hub-Signature-256": github()}, BODY + b" ")


def test_the_wrong_secret_fails():
    with pytest.raises(WebhookSignatureError):
        HmacSignature("other").verify({"X-Hub-Signature-256": github()}, BODY)


def test_any_of_several_secrets_verifies():
    HmacSignature(["new", "s3cret"]).verify({"X-Hub-Signature-256": github()}, BODY)


def test_a_missing_header_fails():
    with pytest.raises(WebhookSignatureError, match="X-Hub-Signature-256 header is missing"):
        HmacSignature("s3cret").verify({}, BODY)


def test_a_header_without_the_prefix_fails():
    bare = github().removeprefix("sha256=")
    with pytest.raises(WebhookSignatureError, match="doesn't start with 'sha256='"):
        HmacSignature("s3cret").verify({"X-Hub-Signature-256": bare}, BODY)


def test_other_headers_digests_and_base64():
    mac = base64.b64encode(hmac.new(b"k", BODY, hashlib.sha1).digest()).decode()
    signature = HmacSignature("k", header="X-Sig", prefix="", digest="sha1", encoding="base64")
    signature.verify({"X-Sig": mac}, BODY)


def test_bytes_secrets():
    HmacSignature(b"s3cret").verify({"X-Hub-Signature-256": github()}, BODY)


@pytest.mark.parametrize(
    ("kwargs", "error"),
    [({"encoding": "b32"}, ValueError), ({"digest": "nope"}, ValueError)],
)
def test_invalid_settings(kwargs, error):
    with pytest.raises(error):
        HmacSignature("s", **kwargs)


def test_at_least_one_secret():
    with pytest.raises(ValueError, match="at least one secret"):
        HmacSignature([])
