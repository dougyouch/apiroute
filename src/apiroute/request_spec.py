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
