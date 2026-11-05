from typing import Any

from apiroute.client import Client
from apiroute.route import route


class TokenEndpoint(Client):
    """An OAuth 2.0 token endpoint: a form POST answered with JSON. Its base_url is the token
    URL itself; OAuth2TokenAuthenticator creates one per fetch, sharing the API client's
    transports, so test mocks and connection pools apply to token requests too."""

    headers = {"Accept": "application/json"}

    @route("POST", "", body_format="form", operation="token")
    def request_token(self, body: dict[str, str]) -> Any: ...
