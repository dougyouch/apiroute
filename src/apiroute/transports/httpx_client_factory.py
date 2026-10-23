import ssl
from typing import Any

import httpx


class HttpxClientFactory:
    """Builds httpx.Clients from one set of httpx.Client options (limits, http2, proxy, ...).

    The SSL context is built once and shared: loading the CA bundle costs about 10 ms per
    client, reusing the context about 0.2 ms, which keeps one-shot clients cheap.
    """

    def __init__(self, **httpx_options: Any):
        self._options = _with_shared_ssl_context(httpx_options)

    def new_client(self) -> httpx.Client:
        return httpx.Client(**self._options)

    def new_async_client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(**self._options)


def _with_shared_ssl_context(options: dict[str, Any]) -> dict[str, Any]:
    options = dict(options)
    verify = options.get("verify", True)
    if verify is False or isinstance(verify, ssl.SSLContext):
        return options
    options["verify"] = httpx.create_ssl_context(
        verify=verify, cert=options.pop("cert", None), trust_env=options.get("trust_env", True)
    )
    return options
