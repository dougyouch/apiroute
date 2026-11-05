from typing import Any

import httpx

from apiroute.api_route_error import ApiRouteError


class OperationFailed(ApiRouteError):
    """A long-running operation a poll= route waited for ended in failure. `status` is the
    status it reported (or None, when an error field said so), `body` the parsed final status
    body and `response` its response."""

    def __init__(self, route_name: str, response: httpx.Response, status: Any, body: Any):
        self.route_name = route_name
        self.response = response
        self.status = status
        self.body = body
        detail = f"status {status!r}" if status is not None else "an error"
        super().__init__(f"{route_name}: the operation ended with {detail}")
