from collections.abc import Callable

from apiroute.testing.mock_call import MockCall
from apiroute.testing.response_source import ResponseSource


class MockRoute:
    """Answers the requests that match it, by operation, method, path or a predicate.

    Its responses are given in order and the last one repeats, so a single response answers
    every matching request.
    """

    def __init__(
        self,
        operation: str | None = None,
        method: str | None = None,
        path: str | None = None,
        where: Callable[[MockCall], bool] | None = None,
    ):
        self._operation = operation
        self._method = method.upper() if method is not None else None
        self._path = path
        self._where = where
        self._responses: list[ResponseSource] = []
        self.calls: list[MockCall] = []

    def respond(self, *responses: ResponseSource) -> "MockRoute":
        self._responses.extend(responses)
        return self

    @property
    def called(self) -> bool:
        return bool(self.calls)

    def matches(self, call: MockCall) -> bool:
        return (
            self._operation in (None, call.operation)
            and self._method in (None, call.method)
            and self._path in (None, call.path)
            and (self._where is None or self._where(call))
        )

    def take(self, call: MockCall) -> ResponseSource:
        """Records call and returns the response source that answers it."""
        if not self._responses:
            raise AssertionError(f"{self!r} matched {call.describe()} but has no response")
        self.calls.append(call)
        return self._responses.pop(0) if len(self._responses) > 1 else self._responses[0]

    def __repr__(self) -> str:
        criteria = {
            "operation": self._operation,
            "method": self._method,
            "path": self._path,
            "where": self._where,
        }
        shown = ", ".join(f"{key}={value!r}" for key, value in criteria.items() if value)
        return f"MockRoute({shown})"
