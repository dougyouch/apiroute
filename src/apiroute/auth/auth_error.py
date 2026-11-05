import httpx

from apiroute.api_route_error import ApiRouteError


class AuthError(ApiRouteError):
    """A credential couldn't be obtained: the token endpoint refused the request or answered
    with something that isn't a token. `error` and `description` hold the OAuth error code and
    text when the endpoint sent them; `response` is its answer, when there was one."""

    def __init__(
        self,
        message: str,
        *,
        response: httpx.Response | None = None,
        error: str | None = None,
        description: str | None = None,
    ):
        super().__init__(message)
        self.response = response
        self.error = error
        self.description = description
