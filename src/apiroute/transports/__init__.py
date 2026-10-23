"""Ways of sending requests, picked per environment with apiroute.use_transport()."""

from apiroute.transports.httpx_client_transport import HttpxClientTransport
from apiroute.transports.one_shot_transport import OneShotTransport
from apiroute.transports.pooled_transport import PooledTransport
from apiroute.transports.thread_local_transport import ThreadLocalTransport
from apiroute.transports.transport import Transport
from apiroute.transports.transport_registry import TransportRegistry

__all__ = [
    "HttpxClientTransport",
    "OneShotTransport",
    "PooledTransport",
    "ThreadLocalTransport",
    "Transport",
    "TransportRegistry",
]
