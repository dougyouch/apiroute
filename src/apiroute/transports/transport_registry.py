import threading
from collections.abc import Callable
from typing import Any

from apiroute.transports.one_shot_transport import OneShotTransport


class TransportRegistry:
    """Which transport each client class uses, set once at startup for the environment.

    A class uses the transport registered for it or its nearest registered base class,
    else the process default (default_factory's unless use() set another). The sync and
    async sides each have a registry of their own.
    """

    def __init__(self, default_factory: Callable[[], Any] = OneShotTransport):
        self._default_factory = default_factory
        self._lock = threading.Lock()
        self._default: Any = None
        self._by_class: dict[type, Any] = {}

    def use(self, transport: Any, client_class: type | None = None) -> None:
        with self._lock:
            if client_class is None:
                self._default = transport
            else:
                self._by_class[client_class] = transport

    def for_class(self, client_class: type) -> Any:
        for base in client_class.__mro__:
            transport = self._by_class.get(base)
            if transport is not None:
                return transport
        return self._default_transport()

    def registered(self) -> list[Any]:
        """Every transport in use: the ones registered per class, then the default."""
        with self._lock:
            transports = [*self._by_class.values(), self._default]
        return [transport for transport in dict.fromkeys(transports) if transport is not None]

    def reset(self) -> None:
        """Forgets every registration, closing nothing; meant for tests."""
        with self._lock:
            self._default = None
            self._by_class = {}

    def _default_transport(self) -> Any:
        with self._lock:
            if self._default is None:
                self._default = self._default_factory()
            return self._default
