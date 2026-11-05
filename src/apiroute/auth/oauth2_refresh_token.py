import time
from collections.abc import Callable, Mapping

from apiroute.auth.access_token import AccessToken
from apiroute.auth.oauth2_token_authenticator import OAuth2TokenAuthenticator


class OAuth2RefreshToken(OAuth2TokenAuthenticator):
    """The OAuth 2.0 refresh token grant (RFC 6749 section 6), for acting on a user's behalf
    after an authorization flow you ran yourself: the refresh token is traded for an access
    token when there's none yet, it expires, or the API rejects it.

        self.authenticator = OAuth2RefreshToken(
            "https://auth.example.com/oauth/token", client_id, refresh_token=stored_token,
            client_secret=client_secret, on_refresh=save_tokens,
        )

    Servers that rotate refresh tokens send a new one with each access token; it replaces the
    old one, and on_refresh, called with every new AccessToken, is where to store it. Pass
    access_token to start with a token you already have. Without a client_secret, only the
    client_id is sent (a public client).
    """

    def __init__(
        self,
        token_url: str,
        client_id: str,
        refresh_token: str,
        *,
        client_secret: str | None = None,
        access_token: AccessToken | None = None,
        on_refresh: Callable[[AccessToken], object] | None = None,
        scope: str | None = None,
        extra: Mapping[str, str] | None = None,
        auth_method: str | None = None,
        leeway: float = 30.0,
        clock: Callable[[], float] = time.monotonic,
    ):
        super().__init__(
            token_url,
            client_id,
            client_secret,
            scope=scope,
            extra=extra,
            auth_method=auth_method,
            leeway=leeway,
            clock=clock,
        )
        self.refresh_token = refresh_token
        self._on_refresh = on_refresh
        if access_token is not None:
            self._store(access_token)

    def grant(self) -> dict[str, str]:
        return {"grant_type": "refresh_token", "refresh_token": self.refresh_token}

    def received(self, token: AccessToken) -> AccessToken:
        if token.refresh_token:
            self.refresh_token = token.refresh_token
        if self._on_refresh is not None:
            self._on_refresh(token)
        return token
