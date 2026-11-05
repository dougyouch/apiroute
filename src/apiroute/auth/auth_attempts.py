import logging
from collections.abc import Callable
from typing import Any, TypeVar

from apiroute.auth.authenticator import Authenticator
from apiroute.request_spec import RequestSpec

logger = logging.getLogger("apiroute")

T = TypeVar("T")

# Turns the request into the one an attempt sends: with the credential applied, or as is
Authorize = Callable[[RequestSpec], RequestSpec]


class AuthAttempts:
    """Runs one attempt of a call with the client's authenticator: the current credential
    applied to the request and, when the attempt's error says the credential was rejected,
    the attempt once more with a fresh one. Without an authenticator, the attempt runs as is.
    """

    def __init__(self, authenticator: Authenticator | None, client: Any, route_name: str):
        self._authenticator = authenticator
        self._client = client
        self._route_name = route_name

    def run(self, attempt: Callable[[Authorize], T]) -> T:
        authenticator = self._authenticator
        if authenticator is None:
            return attempt(_unchanged)
        credential = authenticator.credential(self._client)
        try:
            return attempt(_applying(authenticator, credential))
        except Exception as error:
            if not authenticator.rejects(error):
                raise
            log_rejection(self._route_name, error)
        authenticator.invalidate(credential)
        return attempt(_applying(authenticator, authenticator.credential(self._client)))


def log_rejection(route_name: str, error: Exception) -> None:
    logger.info("%s: credential rejected (%r); sending again with a fresh one", route_name, error)


def _unchanged(request: RequestSpec) -> RequestSpec:
    return request


def _applying(authenticator: Authenticator, credential: Any) -> Authorize:
    return lambda request: authenticator.apply(request, credential)
