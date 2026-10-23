import threading
from collections.abc import Callable

from apiroute.transports.one_shot_transport import OneShotTransport
from apiroute.transports.transport import Transport


class TransportRegistry:
    """Which transport each client class uses, set once at startup for the environment.

    A class uses the transport registered for it or its nearest registered base class,
    else the process default (OneShotTransport unless use() set another).
    """

    def __init__(self, default_factory: Callable[[], Transport] = OneShotTransport):
        self._default_factory = default_factory
        self._lock = threading.Lock()
        self._default: Transport | None = None
        self._by_class: dict[type, Transport] = {}

    def use(self, transport: Transport, client_class: type | None = None) -> None:
        with self._lock:
            if client_class is None:
                self._default = transport
            else:
                self._by_class[client_class] = transport

    def for_class(self, client_class: type) -> Transport:
        for base in client_class.__mro__:
            transport = self._by_class.get(base)
            if transport is not None:
                return transport
        return self._default_transport()

    def close_all(self) -> None:
        with self._lock:
            transports = [*self._by_class.values(), self._default]
        for transport in transports:
            if transport is not None:
                transport.close()

    def reset(self) -> None:
        """Forgets every registration, closing nothing; meant for tests."""
        with self._lock:
            self._default = None
            self._by_class = {}

    def _default_transport(self) -> Transport:
        with self._lock:
            if self._default is None:
                self._default = self._default_factory()
            return self._default
