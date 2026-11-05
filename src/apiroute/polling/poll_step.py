from dataclasses import dataclass

import httpx


@dataclass(frozen=True)
class PollStep:
    """What a poll= route does after a response: wait and poll `url` again, GET `url` for the
    result, or finish with `response`."""

    kind: str  # "wait", "fetch" or "done"
    url: str | None = None
    delay: float = 0.0
    response: httpx.Response | None = None
