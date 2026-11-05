import base64
import json
import re
from dataclasses import dataclass
from typing import Any

import httpx

from apiroute.url_redactor import UrlRedactor

REDACTED = "[REDACTED]"
_REDACT_URL = UrlRedactor()
# Request headers that carry credentials, by name or by a secret-looking part of it
_SECRET_HEADERS = frozenset({"authorization", "proxy-authorization", "cookie"})
_SECRET_PART = re.compile(r"token|secret|key|password|signature|credential|session", re.I)
# Response headers that describe the bytes on the wire, not the decoded body kept
_WIRE_HEADERS = frozenset({"content-encoding", "content-length", "transfer-encoding"})


@dataclass(frozen=True)
class Interaction:
    """One recorded request and its response, as a cassette keeps them: credentials redacted,
    the response body decoded."""

    method: str
    url: str
    request_headers: tuple[tuple[str, str], ...]
    request_body: dict[str, Any]
    status: int
    response_headers: tuple[tuple[str, str], ...]
    response_body: dict[str, Any]

    @classmethod
    def recorded(cls, request: httpx.Request, response: httpx.Response) -> "Interaction":
        return cls(
            method=request.method,
            url=shown_url(request),
            request_headers=tuple(
                (name, REDACTED if _is_secret(name) else value)
                for name, value in request.headers.multi_items()
            ),
            request_body=_body(request.content),
            status=response.status_code,
            response_headers=tuple(
                (name, REDACTED if name.lower() == "set-cookie" else value)
                for name, value in response.headers.multi_items()
                if name.lower() not in _WIRE_HEADERS
            ),
            response_body=_body(response.content),
        )

    @classmethod
    def from_json(cls, data: dict[str, Any]) -> "Interaction":
        request, response = data["request"], data["response"]
        return cls(
            method=request["method"],
            url=request["url"],
            request_headers=tuple(tuple(pair) for pair in request["headers"]),  # type: ignore[misc]
            request_body=request["body"],
            status=response["status"],
            response_headers=tuple(tuple(pair) for pair in response["headers"]),  # type: ignore[misc]
            response_body=response["body"],
        )

    def to_json(self) -> dict[str, Any]:
        return {
            "request": {
                "method": self.method,
                "url": self.url,
                "headers": [list(pair) for pair in self.request_headers],
                "body": self.request_body,
            },
            "response": {
                "status": self.status,
                "headers": [list(pair) for pair in self.response_headers],
                "body": self.response_body,
            },
        }

    def matches(self, request: httpx.Request, match_body: bool) -> bool:
        if (self.method, self.url) != (request.method, shown_url(request)):
            return False
        if not match_body:
            return True
        if "json" in self.request_body:  # kept parsed, so compared parsed: spacing may differ
            try:
                return bool(json.loads(request.content) == self.request_body["json"])
            except ValueError:
                return False
        return _content(self.request_body) == request.content

    def response(self, request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            self.status,
            headers=list(self.response_headers),
            content=_content(self.response_body),
            request=request,
        )


def shown_url(request: httpx.Request) -> str:
    """The URL as a cassette keeps it, secrets in the query masked: a live request is matched
    by its URL redacted the same way."""
    return _REDACT_URL.redact(str(request.url))


def _is_secret(name: str) -> bool:
    return name.lower() in _SECRET_HEADERS or bool(_SECRET_PART.search(name))


def _body(content: bytes) -> dict[str, Any]:
    if not content:
        return {}
    try:
        text = content.decode()
    except UnicodeDecodeError:
        return {"base64": base64.b64encode(content).decode("ascii")}
    try:
        return {"json": json.loads(text)} if text.lstrip()[:1] in "{[" else {"text": text}
    except ValueError:
        return {"text": text}


def _content(body: dict[str, Any]) -> bytes:
    if "json" in body:
        return json.dumps(body["json"]).encode()
    if "text" in body:
        return body["text"].encode()
    if "base64" in body:
        return base64.b64decode(body["base64"])
    return b""
