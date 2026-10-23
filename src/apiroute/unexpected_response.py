import httpx

from apiroute.api_route_error import ApiRouteError


class UnexpectedResponse(ApiRouteError):
    """The server answered with a status the route doesn't expect."""

    def __init__(self, route_name: str, response: httpx.Response):
        self.route_name = route_name
        self.response = response
        self.status_code = response.status_code
        self.request = response.request
        super().__init__(
            f"{route_name}: unexpected status {response.status_code} "
            f"from {response.request.method} {response.request.url}"
        )
