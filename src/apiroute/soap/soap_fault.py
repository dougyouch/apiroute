from typing import Any

import httpx

from apiroute.api_route_error import ApiRouteError


class SoapFault(ApiRouteError):
    """The service answered with a SOAP Fault (or an error status with no envelope)."""

    def __init__(self, code: str, reason: str, detail: Any, response: httpx.Response):
        self.code = code
        self.reason = reason
        self.detail = detail
        self.response = response
        super().__init__(f"SOAP fault {code}: {reason}")
