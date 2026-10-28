from fnmatch import fnmatchcase
from typing import Any

from apiroute.codegen.pagination.operation_facts import OperationFacts
from apiroute.codegen.pagination.strategy_call import StrategyCall

_KEYS = frozenset({"name", "operations", "method", "has_parameter", "response", "paginate"})


class PaginationRule:
    """One rule of a --pagination file: which operations it picks (by operation ID pattern,
    method, parameters and response shape, all of which must hold) and how they page."""

    def __init__(self, raw: Any, label: str):
        if not isinstance(raw, dict):
            raise ValueError(f"{label}: expected an object")
        self.label = f"{label} ({raw['name']})" if raw.get("name") else label
        unknown = sorted(set(raw) - _KEYS)
        if unknown:
            raise ValueError(f"{self.label}: unknown keys {', '.join(unknown)}")
        self.strategy = self._strategy(raw.get("paginate"))
        self._operations = _strings(raw.get("operations", []), self.label, "operations")
        methods = _strings(raw.get("method", ["GET"]), self.label, "method")
        self._methods = {method.upper() for method in methods}
        self._parameters = set(_strings(raw.get("has_parameter", []), self.label, "has_parameter"))
        self._response = self._response_shape(raw.get("response"))
        self.matched = 0

    def matches(self, facts: OperationFacts) -> bool:
        if self._operations and not any(
            fnmatchcase(facts.operation_id, pattern) for pattern in self._operations
        ):
            return False
        if facts.method not in self._methods or not self._parameters <= facts.parameters:
            return False
        if self._response == "array":
            return facts.is_array
        return self._response is None or set(self._response["has"]) <= facts.properties

    def _strategy(self, paginate: Any) -> StrategyCall:
        if not isinstance(paginate, dict) or "type" not in paginate:
            raise ValueError(f"{self.label}: paginate needs an object with a type")
        arguments = {key: value for key, value in paginate.items() if key != "type"}
        try:
            return StrategyCall(paginate["type"], arguments)
        except ValueError as error:
            raise ValueError(f"{self.label}: {error}") from error

    def _response_shape(self, response: Any) -> Any:
        if response is None or response == "array":
            return response
        if isinstance(response, dict) and set(response) == {"has"}:
            _strings(response["has"], self.label, "response.has")
            return response
        raise ValueError(f'{self.label}: response is "array" or {{"has": [names]}}')


def _strings(value: Any, label: str, key: str) -> list[str]:
    values = [value] if isinstance(value, str) else value
    if not isinstance(values, list) or not all(isinstance(v, str) for v in values):
        raise ValueError(f"{label}: {key} is a name or a list of names")
    return values
