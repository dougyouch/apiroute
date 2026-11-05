import base64
from urllib.parse import quote_plus

# How a client proves who it is to the token endpoint (RFC 6749 section 2.3.1)
CLIENT_AUTH_METHODS = ("basic", "post", "none")


class OAuth2ClientAuth:
    """Adds the client's credentials to a token request: "basic" sends them in an
    Authorization header (client_secret_basic, which servers must accept), "post" as
    client_id and client_secret form fields (client_secret_post), and "none" sends only
    client_id, for public clients that have no secret."""

    def __init__(self, client_id: str, client_secret: str | None, method: str | None):
        method = method or ("none" if client_secret is None else "basic")
        if method not in CLIENT_AUTH_METHODS:
            raise ValueError(f"auth_method must be one of {CLIENT_AUTH_METHODS}")
        if method != "none" and client_secret is None:
            raise ValueError(f"auth_method={method!r} needs a client_secret")
        self._client_id = client_id
        self._client_secret = client_secret
        self._method = method

    def form(self) -> dict[str, str]:
        if self._method == "basic":
            return {}
        if self._method == "post":
            return {"client_id": self._client_id, "client_secret": str(self._client_secret)}
        return {"client_id": self._client_id}

    def headers(self) -> dict[str, str]:
        if self._method != "basic":
            return {}
        # Each part is form-encoded before joining, as RFC 6749 section 2.3.1 says
        pair = f"{quote_plus(self._client_id)}:{quote_plus(str(self._client_secret))}"
        return {"Authorization": "Basic " + base64.b64encode(pair.encode()).decode("ascii")}
