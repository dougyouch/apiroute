import inspect
from typing import Any

from apiroute.transports.async_one_shot_transport import AsyncOneShotTransport
from apiroute.transports.transport_registry import TransportRegistry

# The process-wide registries, one for sync calls and one for client.aio calls.
# Configure them once at startup, e.g. in a worker's boot code.
TRANSPORTS = TransportRegistry()
ASYNC_TRANSPORTS = TransportRegistry(AsyncOneShotTransport)


def use_transport(transport: Any, client: type | None = None) -> None:
    """Sends requests through transport: for every client, or for one client class
    (and its subclasses) when client is given. An async transport (one whose send is a
    coroutine) applies to client.aio calls, a sync one to plain calls."""
    registry_for(transport).use(transport, client)


def close_transports() -> None:
    """Closes the connections of every registered sync transport, e.g. at shutdown."""
    for transport in TRANSPORTS.registered():
        transport.close()


async def aclose_transports() -> None:
    """Closes the connections of every registered async transport, from the running loop."""
    for transport in ASYNC_TRANSPORTS.registered():
        await transport.aclose()


def is_async_transport(transport: Any) -> bool:
    return inspect.iscoroutinefunction(transport.send)


def registry_for(transport: Any) -> TransportRegistry:
    return ASYNC_TRANSPORTS if is_async_transport(transport) else TRANSPORTS
