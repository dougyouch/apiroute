import json
from dataclasses import dataclass
from typing import Any

import httpx

from apiroute.request_spec import RequestSpec


@dataclass(frozen=True)
class MockCall:
    """One request a MockTransport answered: the RequestSpec apiroute built, and the
    httpx.Request httpx encoded from it, as it would have gone on the wire."""

    spec: RequestSpec
    request: httpx.Request

    @property
    def operation(self) -> str:
        return self.spec.operation

    @property
    def method(self) -> str:
        return self.request.method

    @property
    def url(self) -> httpx.URL:
        return self.request.url

    @property
    def path(self) -> str:
        return self.request.url.path

    @property
    def params(self) -> httpx.QueryParams:
        return self.request.url.params

    @property
    def headers(self) -> httpx.Headers:
        return self.request.headers

    @property
    def content(self) -> bytes:
        return self.request.content

    def json(self) -> Any:
        return json.loads(self.request.content)

    @property
    def graphql_variables(self) -> Any:
        """The variables a GraphQL request sent, or None when its body isn't a JSON object."""
        try:
            body = self.json()
        except ValueError:
            return None
        return body.get("variables") if isinstance(body, dict) else None

    def describe(self) -> str:
        return f"{self.operation or '(no operation)'}: {self.method} {self.url}"
