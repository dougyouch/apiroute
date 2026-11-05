import pytest

from apiroute.auth import AccessToken, AuthError


def test_reads_a_full_token_response():
    token = AccessToken.from_reply(
        {
            "access_token": "abc",
            "token_type": "Bearer",
            "expires_in": 3600,
            "refresh_token": "r",
            "scope": "read write",
        }
    )
    assert token == AccessToken("abc", 3600.0, "Bearer", "r", "read write")


def test_only_access_token_is_required():
    assert AccessToken.from_reply({"access_token": "abc"}) == AccessToken("abc")


@pytest.mark.parametrize("token_type", ["bearer", "BEARER", None, ""])
def test_bearer_in_any_case_is_sent_as_Bearer(token_type):
    token = AccessToken.from_reply({"access_token": "abc", "token_type": token_type})
    assert token.authorization == "Bearer abc"


def test_other_token_types_are_kept():
    token = AccessToken.from_reply({"access_token": "abc", "token_type": "DPoP"})
    assert token.authorization == "DPoP abc"


def test_expires_in_may_be_text():
    assert AccessToken.from_reply({"access_token": "a", "expires_in": "60"}).expires_in == 60.0


def test_expires_in_that_isnt_a_number_fails():
    with pytest.raises(AuthError, match="expires_in"):
        AccessToken.from_reply({"access_token": "a", "expires_in": "soon"})


def test_a_boolean_expires_in_is_ignored():
    assert AccessToken.from_reply({"access_token": "a", "expires_in": True}).expires_in is None


@pytest.mark.parametrize("reply", [{}, {"access_token": 5}, [], "token", None])
def test_a_reply_without_an_access_token_fails(reply):
    with pytest.raises(AuthError, match="no access_token"):
        AccessToken.from_reply(reply)
