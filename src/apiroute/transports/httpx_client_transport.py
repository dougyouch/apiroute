from contextlib import AbstractContextManager

import httpx

from apiroute.request_spec import RequestSpec


class HttpxClientTransport:
    """Sends through an httpx.Client you own, e.g. one with a MockTransport in tests.

    close() leaves the client open; closing it is up to its owner.
    """

    def __init__(self, http_client: httpx.Client):
        self.http_client = http_client

    def send(self, spec: RequestSpec) -> httpx.Response:
        return self.http_client.request(spec.method, spec.url, **request_arguments(spec))

    def stream(self, spec: RequestSpec) -> AbstractContextManager[httpx.Response]:
        return self.http_client.stream(spec.method, spec.url, **request_arguments(spec))

    def close(self) -> None:
        pass


def request_arguments(spec: RequestSpec) -> dict:
    return {
        "headers": spec.headers,
        "params": spec.params,
        "content": spec.content,
        "timeout": spec.timeout,
    }
