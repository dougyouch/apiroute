import time
from collections.abc import Callable, Mapping
from typing import Any

from apiroute.auth.access_token import AccessToken
from apiroute.auth.oauth2_client_auth import OAuth2ClientAuth
from apiroute.auth.token_authenticator import TokenAuthenticator
from apiroute.auth.token_endpoint import TokenEndpoint
from apiroute.auth.token_error import token_error
from apiroute.base_url_validator import validate_base_url
from apiroute.shared_transports import shared_transports
from apiroute.unexpected_response import UnexpectedResponse


class OAuth2TokenAuthenticator(TokenAuthenticator):
    """A TokenAuthenticator that gets its tokens from an OAuth 2.0 token endpoint. Subclasses
    say which grant to request in grant(); the client's credentials, scope and extra fields
    (such as an audience or resource) are added to every request.

    A refusal from the endpoint raises AuthError, which isn't retried; a network failure
    raises httpx's error, which the API call's retries may retry.
    """

    def __init__(
        self,
        token_url: str,
        client_id: str,
        client_secret: str | None = None,
        *,
        scope: str | None = None,
        extra: Mapping[str, str] | None = None,
        auth_method: str | None = None,
        leeway: float = 30.0,
        clock: Callable[[], float] = time.monotonic,
    ):
        super().__init__(leeway=leeway, clock=clock)
        validate_base_url(token_url)
        self.token_url = token_url
        self._client_auth = OAuth2ClientAuth(client_id, client_secret, auth_method)
        self._scope = scope
        self._extra = dict(extra or {})

    def grant(self) -> dict[str, str]:
        """The grant's own form fields, e.g. {"grant_type": "client_credentials"}."""
        raise NotImplementedError

    def received(self, token: AccessToken) -> AccessToken:
        """Called with each new token before it is used; returns the token to keep."""
        return token

    def fetch_token(self, client: Any) -> AccessToken:
        endpoint = self._endpoint(client).with_options(headers=self._client_auth.headers())
        try:
            reply = endpoint.request_token(self._form())
        except UnexpectedResponse as error:
            raise token_error(error) from None
        return self.received(AccessToken.from_reply(reply))

    async def afetch_token(self, client: Any) -> AccessToken:
        endpoint = self._endpoint(client).with_options(headers=self._client_auth.headers())
        try:
            reply = await endpoint.aio.request_token(self._form())
        except UnexpectedResponse as error:
            raise token_error(error) from None
        return self.received(AccessToken.from_reply(reply))

    def _form(self) -> dict[str, str]:
        form = {**self._extra, **self.grant(), **self._client_auth.form()}
        if self._scope is not None:
            form["scope"] = self._scope
        return form

    def _endpoint(self, client: Any) -> TokenEndpoint:
        return TokenEndpoint(base_url=self.token_url, **shared_transports(client))
