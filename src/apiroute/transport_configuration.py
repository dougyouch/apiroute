from apiroute.transports.transport import Transport
from apiroute.transports.transport_registry import TransportRegistry

# The process-wide registry: configure it once at startup, e.g. in a worker's boot code
TRANSPORTS = TransportRegistry()


def use_transport(transport: Transport, client: type | None = None) -> None:
    """Sends requests through transport: for every client, or for one client class
    (and its subclasses) when client is given."""
    TRANSPORTS.use(transport, client)


def close_transports() -> None:
    """Closes the connections of every registered transport, e.g. at shutdown."""
    TRANSPORTS.close_all()
