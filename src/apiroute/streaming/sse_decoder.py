import httpx

from apiroute.streaming.server_sent_event import ServerSentEvent


class SseDecoder:
    """Turns the lines of a text/event-stream body into ServerSentEvents, as the HTML standard's
    event stream parsing does: a blank line dispatches the fields seen since the last one, a
    line starting with ':' is a comment, and an event without data is not dispatched.

    It also keeps what a reconnect needs: the last event ID and the server's retry time.
    """

    def __init__(self) -> None:
        self.last_event_id = ""
        # The reconnection time in milliseconds a `retry:` field asked for, if any
        self.retry: int | None = None
        self._id_buffer = ""
        self._clear_event()

    def encoding(self, response: httpx.Response) -> str:
        """Event streams are always UTF-8; a leading byte order mark is dropped."""
        return "utf-8-sig"

    def feed(self, line: str) -> list[ServerSentEvent]:
        if not line:
            return self._dispatch()
        if line.startswith(":"):
            return []
        name, _, value = line.partition(":")
        self._field(name, value[1:] if value.startswith(" ") else value)
        return []

    def end(self) -> list[ServerSentEvent]:
        """An event the body ended in the middle of is dropped, as the standard says."""
        self._clear_event()
        return []

    def reset(self) -> None:
        """Forgets a partly received event before reading a reconnected stream."""
        self._clear_event()
        self._id_buffer = self.last_event_id

    def _field(self, name: str, value: str) -> None:
        if name == "data":
            self._data.append(value)
        elif name == "event":
            self._event = value
        elif name == "id" and "\0" not in value:
            self._id_buffer = value
        elif name == "retry" and value.isascii() and value.isdigit():
            self.retry = int(value)

    def _dispatch(self) -> list[ServerSentEvent]:
        self.last_event_id = self._id_buffer
        data, event = self._data, self._event
        self._clear_event()
        if not data:
            return []
        return [ServerSentEvent("\n".join(data), event or "message", self.last_event_id or None)]

    def _clear_event(self) -> None:
        self._data: list[str] = []
        self._event = ""
