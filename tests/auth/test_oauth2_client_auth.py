import base64

import pytest

from apiroute.auth.oauth2_client_auth import OAuth2ClientAuth


def decoded(headers):
    return base64.b64decode(headers["Authorization"].removeprefix("Basic ")).decode()


def test_basic_is_the_default_with_a_secret():
    auth = OAuth2ClientAuth("id", "secret", None)
    assert decoded(auth.headers()) == "id:secret"
    assert auth.form() == {}


def test_basic_form_encodes_each_part():
    auth = OAuth2ClientAuth("my id", "s:e/c+ret", "basic")
    assert decoded(auth.headers()) == "my+id:s%3Ae%2Fc%2Bret"


def test_post_sends_the_credentials_as_form_fields():
    auth = OAuth2ClientAuth("id", "secret", "post")
    assert auth.form() == {"client_id": "id", "client_secret": "secret"}
    assert auth.headers() == {}


def test_none_is_the_default_without_a_secret():
    auth = OAuth2ClientAuth("id", None, None)
    assert auth.form() == {"client_id": "id"}
    assert auth.headers() == {}


def test_unknown_methods_fail():
    with pytest.raises(ValueError, match="auth_method must be one of"):
        OAuth2ClientAuth("id", "secret", "jwt")


@pytest.mark.parametrize("method", ["basic", "post"])
def test_methods_that_send_a_secret_need_one(method):
    with pytest.raises(ValueError, match="needs a client_secret"):
        OAuth2ClientAuth("id", None, method)
