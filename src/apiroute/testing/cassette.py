import json
import threading
from collections.abc import Callable
from pathlib import Path
from typing import Any

import httpx

from apiroute.testing.cassette_mismatch import CassetteMismatch
from apiroute.testing.interaction import Interaction, shown_url

FORMAT_VERSION = 1


class Cassette:
    """A file of recorded interactions (JSON), and the state of recording or replaying it."""

    def __init__(
        self,
        path: str | Path,
        *,
        match_body: bool = False,
        redact: Callable[[dict[str, Any]], dict[str, Any]] | None = None,
    ):
        self.path = Path(path)
        self.interactions: list[Interaction] = []
        self._played: set[int] = set()
        self._match_body = match_body
        self._redact = redact
        self._lock = threading.Lock()

    @property
    def exists(self) -> bool:
        return self.path.exists()

    @property
    def unplayed(self) -> list[Interaction]:
        """Recorded interactions no request has replayed yet."""
        return [i for n, i in enumerate(self.interactions) if n not in self._played]

    def load(self) -> None:
        data = json.loads(self.path.read_text())
        if data.get("version") != FORMAT_VERSION:
            raise ValueError(f"{self.path}: not a version {FORMAT_VERSION} apiroute cassette")
        self.interactions = [Interaction.from_json(item) for item in data["interactions"]]

    def save(self) -> None:
        items = [self._redacted(i.to_json()) for i in self.interactions]
        document = {"version": FORMAT_VERSION, "interactions": items}
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(document, indent=2, ensure_ascii=False) + "\n")

    def record(self, response: httpx.Response) -> None:
        with self._lock:
            self.interactions.append(Interaction.recorded(response.request, response))

    def play(self, request: httpx.Request) -> httpx.Response:
        """The response recorded for the first unplayed interaction matching the request."""
        with self._lock:
            for index, interaction in enumerate(self.interactions):
                if index not in self._played and interaction.matches(request, self._match_body):
                    self._played.add(index)
                    return interaction.response(request)
        raise CassetteMismatch(
            f"{self.path}: no unplayed recording of {request.method} {shown_url(request)}"
        )

    def _redacted(self, item: dict[str, Any]) -> dict[str, Any]:
        return item if self._redact is None else self._redact(item)
