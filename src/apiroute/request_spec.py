from dataclasses import dataclass


@dataclass(frozen=True)
class RequestSpec:
    """Everything needed to send one request, built without any I/O."""

    method: str
    url: str
    headers: dict[str, str]
    params: list[tuple[str, str]]
    content: bytes | str | None
    timeout: float | None
    # The API's own name for the operation (an OpenAPI operationId, a WSDL operation), else
    # the route's method name: for on_request/on_response, e.g. to add eBay's callname
    operation: str = ""
    # Whether a 3xx answer is followed; None leaves it to the transport's httpx client
    follow_redirects: bool | None = None
