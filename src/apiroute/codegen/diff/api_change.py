from dataclasses import dataclass

BREAKING, ADDITION = "breaking", "addition"


@dataclass(frozen=True, order=True)
class ApiChange:
    """One difference between two generated clients: breaking (code using the old client may
    fail with the new one) or an addition (the new client offers more)."""

    kind: str  # BREAKING or ADDITION
    subject: str  # what changed: "GET /pets/{}", "model Pet", "Pet.name"
    detail: str  # how, e.g. "removed", "type str -> int"

    def __str__(self) -> str:
        return f"{self.subject}: {self.detail}"
