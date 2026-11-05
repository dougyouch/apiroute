from typing import Any

from apiroute.caching.async_caching_transport import AsyncCachingTransport
from apiroute.caching.caching_transport import CachingTransport
from apiroute.client_config import ClientConfig
from apiroute.rate_limiting.async_rate_limited_transport import AsyncRateLimitedTransport
from apiroute.rate_limiting.rate_limited_transport import RateLimitedTransport
from apiroute.telemetry.async_traced_transport import AsyncTracedTransport
from apiroute.telemetry.traced_transport import TracedTransport


class TransportPipeline:
    """Wraps a call's transport in what the client's settings ask for. From the outside in: the
    conditional cache, the rate limiter, then the telemetry span around the request itself, so
    a revalidation still waits for the rate limiter and the span times only the exchange."""

    def __init__(self, config: ClientConfig, client: Any):
        self._config = config
        self._client = client

    def wrap(self, transport: Any) -> Any:
        config = self._config
        if config.telemetry is not None:
            transport = TracedTransport(transport, config.telemetry, self._client.redact_url)
        if config.rate_limiter is not None:
            transport = RateLimitedTransport(transport, config.rate_limiter, self._client._sleep)
        if config.conditional_cache is not None:
            transport = CachingTransport(transport, config.conditional_cache)
        return transport

    def wrap_async(self, transport: Any) -> Any:
        config = self._config
        if config.telemetry is not None:
            transport = AsyncTracedTransport(transport, config.telemetry, self._client.redact_url)
        if config.rate_limiter is not None:
            transport = AsyncRateLimitedTransport(
                transport, config.rate_limiter, self._client._async_sleep
            )
        if config.conditional_cache is not None:
            transport = AsyncCachingTransport(transport, config.conditional_cache)
        return transport
