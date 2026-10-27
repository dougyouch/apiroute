import uuid

from apiroute.client_config import ClientConfig
from apiroute.route_definition import RouteDefinition


class IdempotencyKey:
    """The idempotency-key header a route's calls carry, if any: the route's own header name,
    or for a route that isn't idempotent, its class's idempotency_key, unless the route turned
    it off (idempotency_key=False). A call sends one fresh key, the same on every retry, so
    the server can run the request once however many attempts reach it."""

    def __init__(self, definition: RouteDefinition, config: ClientConfig):
        self._definition = definition
        self._config = config

    @property
    def header_name(self) -> str | None:
        own = self._definition.idempotency_key
        if own is False:
            return None
        if isinstance(own, str):
            return own
        return None if self._definition.idempotent else self._config.idempotency_key

    def sent_in(self, headers: dict[str, str]) -> bool:
        """Whether a request with these headers carries the key (generated, or the caller's
        own), so retrying it is safe; not when the caller removed the header."""
        name = self.header_name
        return name is not None and name.lower() in {header.lower() for header in headers}

    @staticmethod
    def new_value() -> str:
        return str(uuid.uuid4())
