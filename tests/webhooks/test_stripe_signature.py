import hashlib
import hmac

import pytest

from apiroute.webhooks import StripeSignature, WebhookSignatureError

BODY = b'{"type": "invoice.paid"}'
NOW = 1_700_000_000


def header(secret=b"whsec_test", timestamp=NOW, body=BODY, extra=""):
    signed = f"{timestamp}.".encode() + body
    v1 = hmac.new(secret, signed, hashlib.sha256).hexdigest()
    return f"t={timestamp},v1={v1}{extra}"


def stripe(secret="whsec_test", **kwargs):
    return StripeSignature(secret, clock=lambda: NOW, **kwargs)


def test_a_valid_signature_verifies():
    stripe().verify({"Stripe-Signature": header()}, BODY)


def test_any_v1_entry_may_match():
    sent = f"t={NOW},v1=deadbeef," + header().split(",", 1)[1]
    stripe().verify({"Stripe-Signature": sent}, BODY)


def test_v0_entries_are_ignored():
    stripe().verify({"Stripe-Signature": header(extra=",v0=abc")}, BODY)


def test_rotated_secrets():
    stripe(["whsec_new", "whsec_test"]).verify({"Stripe-Signature": header()}, BODY)


def test_a_tampered_body_fails():
    with pytest.raises(WebhookSignatureError, match="no v1 signature matches"):
        stripe().verify({"Stripe-Signature": header()}, BODY + b"x")


@pytest.mark.parametrize("age", [301, -301])
def test_a_timestamp_outside_the_tolerance_fails(age):
    with pytest.raises(WebhookSignatureError, match="outside the tolerance"):
        stripe().verify({"Stripe-Signature": header(timestamp=NOW - age)}, BODY)


def test_the_tolerance_can_be_widened():
    stripe(tolerance=600).verify({"Stripe-Signature": header(timestamp=NOW - 500)}, BODY)


@pytest.mark.parametrize(
    ("sent", "problem"),
    [
        (None, "header is missing"),
        ("v1=abc", "no timestamp"),
        ("t=soon,v1=abc", "no timestamp"),
        (f"t={NOW}", "no v1 signature"),
    ],
)
def test_malformed_headers_fail(sent, problem):
    headers = {} if sent is None else {"Stripe-Signature": sent}
    with pytest.raises(WebhookSignatureError, match=problem):
        stripe().verify(headers, BODY)
