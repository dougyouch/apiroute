from collections.abc import Awaitable, Callable
from typing import Any, TypeVar

from apiroute.auth.auth_attempts import Authorize, log_rejection
from apiroute.auth.authenticator import Authenticator
from apiroute.request_spec import RequestSpec

T = TypeVar("T")


class AsyncAuthAttempts:
    """AuthAttempts for async calls: credentials come from acredential()."""

    def __init__(self, authenticator: Authenticator | None, client: Any, route_name: str):
        self._authenticator = authenticator
        self._client = client
        self._route_name = route_name

    async def run(self, attempt: Callable[[Authorize], Awaitable[T]]) -> T:
        authenticator = self._authenticator
        if authenticator is None:
            return await attempt(_unchanged)
        credential = await authenticator.acredential(self._client)
        try:
            return await attempt(_applying(authenticator, credential))
        except Exception as error:
            if not authenticator.rejects(error):
                raise
            log_rejection(self._route_name, error)
        authenticator.invalidate(credential)
        fresh = await authenticator.acredential(self._client)
        return await attempt(_applying(authenticator, fresh))


def _unchanged(request: RequestSpec) -> RequestSpec:
    return request


def _applying(authenticator: Authenticator, credential: Any) -> Authorize:
    return lambda request: authenticator.apply(request, credential)
