import httpx

from apiroute.api_route_error import ApiRouteError


class UnexpectedResponse(ApiRouteError):
    """The server answered with a status the route doesn't expect, or with a body that isn't
    the JSON the route expects."""

    def __init__(
        self,
        route_name: str,
        response: httpx.Response,
        reason: str | None = None,
        *,
        shown_url: str | None = None,
    ):
        self.route_name = route_name
        self.response = response
        self.status_code = response.status_code
        self.request = response.request
        problem = reason or f"unexpected status {response.status_code}"
        url = shown_url if shown_url is not None else str(response.request.url)
        super().__init__(f"{route_name}: {problem} from {response.request.method} {url}")
