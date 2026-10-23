import httpx

from apiroute.api_route_error import ApiRouteError


class ResponseValidationError(ApiRouteError):
    """A response body couldn't be converted to the route's model type."""

    def __init__(self, route_name: str, response: httpx.Response, error: Exception):
        self.route_name = route_name
        self.response = response
        self.error = error
        super().__init__(f"{route_name}: response doesn't match its model: {error}")
