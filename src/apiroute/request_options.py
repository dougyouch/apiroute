from collections.abc import Mapping
from dataclasses import dataclass, replace
from typing import Any

from apiroute.retries import Retries

RETURN_MODES = ("json", "text", "bytes", "response")


@dataclass(frozen=True)
class RequestOptions:
    """Per-request overrides from with_options; None means "not overridden".

    retries may be a Retries or an int, which replaces only the number of attempts.
    A None header value drops that header. A dict body is merged over the route's dict body
    (shallow, a None value removes that key); any other body replaces it.
    """

    headers: Mapping[str, Any] | None = None
    query: Mapping[str, Any] | None = None
    body: Any = None
    timeout: float | None = None
    retries: Retries | int | None = None
    returns: str | None = None

    def __post_init__(self) -> None:
        if self.returns is not None and self.returns not in RETURN_MODES:
            raise ValueError(f"returns must be one of {RETURN_MODES}")

    def merged(self, other: "RequestOptions") -> "RequestOptions":
        return replace(
            self,
            headers=_merge(self.headers, other.headers),
            query=_merge(self.query, other.query),
            body=_merge_body(self.body, other.body),
            timeout=_pick(self.timeout, other.timeout),
            retries=_pick(self.retries, other.retries),
            returns=_pick(self.returns, other.returns),
        )


def _merge(base: Mapping | None, override: Mapping | None) -> Mapping | None:
    if base is None or override is None:
        return override if base is None else base
    return {**base, **override}


def _merge_body(base: Any, override: Any) -> Any:
    """Chained dict bodies merge, keeping None values so they still remove route keys."""
    if isinstance(base, Mapping) and isinstance(override, Mapping):
        return {**base, **override}
    return _pick(base, override)


def _pick(base: Any, override: Any) -> Any:
    return base if override is None else override
