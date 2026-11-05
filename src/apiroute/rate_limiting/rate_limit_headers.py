import re
from collections.abc import Callable

import httpx

# A reset value this large is a Unix time (GitHub, X) rather than seconds from now
_UNIX_TIME = 1_000_000_000
_UNIX_TIME_MS = 1_000_000_000_000
# The `RateLimit: "default";r=0;t=30` field of the IETF RateLimit header fields draft
_PARAM = re.compile(r";\s*([rt])\s*=\s*(\d+(?:\.\d+)?)")
_LIMITED_STATUSES = (429, 503)


class RateLimitHeaders:
    """Reads how long a response says to stop sending for: when its remaining quota is spent,
    until the quota resets, and after a 429 or 503, for its Retry-After.

    It understands the IETF draft's `RateLimit` field (r= remaining, t= seconds to reset) and
    its older `RateLimit-Remaining`/`RateLimit-Reset`, and the common `X-RateLimit-Remaining`/
    `X-RateLimit-Reset`, whose reset may be seconds from now or a Unix time in seconds or ms.
    """

    def __init__(self, wall_clock: Callable[[], float]):
        self._wall_clock = wall_clock

    def pause(self, response: httpx.Response) -> float | None:
        """Seconds to stop sending for, or None when the response asks for no pause."""
        if response.status_code in _LIMITED_STATUSES:
            retry_after = _number(response.headers.get("Retry-After"))
            if retry_after is not None:
                return retry_after
        remaining, reset = self._quota(response.headers)
        if remaining is None or remaining > 0 or reset is None:
            return None
        return reset

    def _quota(self, headers: httpx.Headers) -> tuple[float | None, float | None]:
        field = headers.get("RateLimit")
        if field is not None:
            params = dict(_PARAM.findall(field.split(",")[0]))
            return _number(params.get("r")), _number(params.get("t"))
        for prefix in ("RateLimit-", "X-RateLimit-"):
            remaining = _number(headers.get(prefix + "Remaining"))
            if remaining is not None:
                return remaining, self._seconds(_number(headers.get(prefix + "Reset")))
        return None, None

    def _seconds(self, reset: float | None) -> float | None:
        if reset is None:
            return None
        if reset >= _UNIX_TIME_MS:
            reset /= 1000
        if reset >= _UNIX_TIME:
            return max(0.0, reset - self._wall_clock())
        return reset


def _number(value: str | None) -> float | None:
    if value is None:
        return None
    try:
        number = float(value)
    except ValueError:
        return None
    return number if number >= 0 else None
