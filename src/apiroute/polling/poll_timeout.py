from apiroute.api_route_error import ApiRouteError


class PollTimeout(ApiRouteError):
    """A long-running operation a poll= route waited for didn't finish within the Poll's
    timeout. `url` is the status URL last polled, as redact_url shows it."""

    def __init__(self, route_name: str, timeout: float, url: str):
        self.route_name = route_name
        self.timeout = timeout
        self.url = url
        super().__init__(f"{route_name}: the operation didn't finish within {timeout:g}s ({url})")
