import json
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ServerSentEvent:
    """One event from a text/event-stream body, as a stream="sse" route yields it."""

    data: str
    # The event's type: its `event:` field, else "message"
    event: str = "message"
    # The last event ID the stream set, sent back as Last-Event-ID on a reconnect
    id: str | None = None

    def json(self) -> Any:
        """The data parsed as JSON, for APIs that send a JSON object per event."""
        return json.loads(self.data)
