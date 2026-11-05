import threading
import time
from collections.abc import Callable
from dataclasses import replace
from typing import Any

from apiroute.auth.access_token import AccessToken
from apiroute.auth.authenticator import Authenticator
from apiroute.auth.loop_locks import LoopLocks
from apiroute.request_spec import RequestSpec


class TokenAuthenticator(Authenticator):
    """An Authenticator for tokens that expire: it keeps the current AccessToken, fetches a new
    one `leeway` seconds before it expires (or half its lifetime, if that is shorter) or after
    the API rejects it, and sends it as an Authorization header.

    Subclasses implement fetch_token(), and afetch_token() for async calls (by default it calls
    fetch_token()). Concurrent calls wait for one fetch rather than each fetching: one lock for
    sync calls in every thread, and one per event loop for async calls.
    """

    def __init__(self, *, leeway: float = 30.0, clock: Callable[[], float] = time.monotonic):
        self._leeway = leeway
        self._clock = clock
        self._lock = threading.Lock()
        self._loop_locks = LoopLocks()
        # (token, deadline) in one attribute, so a reader never sees half of an update
        self._current: tuple[AccessToken | None, float | None] = (None, None)

    def fetch_token(self, client: Any) -> AccessToken:
        """A new token. `client` is the API client making the call."""
        raise NotImplementedError

    async def afetch_token(self, client: Any) -> AccessToken:
        """fetch_token() for async calls; override when fetching does I/O."""
        return self.fetch_token(client)

    @property
    def token(self) -> AccessToken | None:
        """The token held now, fresh or not; None before the first fetch."""
        return self._current[0]

    def credential(self, client: Any) -> AccessToken:
        token = self._fresh_token()
        if token is not None:
            return token
        with self._lock:
            token = self._fresh_token()  # another thread may have fetched it while we waited
            if token is None:
                token = self._store(self.fetch_token(client))
        return token

    async def acredential(self, client: Any) -> AccessToken:
        token = self._fresh_token()
        if token is not None:
            return token
        async with self._loop_locks.current():
            token = self._fresh_token()
            if token is None:
                token = self._store(await self.afetch_token(client))
        return token

    def apply(self, request: RequestSpec, credential: AccessToken) -> RequestSpec:
        headers = {**request.headers, "Authorization": credential.authorization}
        return replace(request, headers=headers)

    def invalidate(self, credential: Any) -> None:
        if self._current[0] is credential:
            self._current = (None, None)

    def _fresh_token(self) -> AccessToken | None:
        token, deadline = self._current
        if token is None or (deadline is not None and self._clock() >= deadline):
            return None
        return token

    def _store(self, token: AccessToken) -> AccessToken:
        self._current = (token, self._deadline(token))
        return token

    def _deadline(self, token: AccessToken) -> float | None:
        if token.expires_in is None:
            return None
        margin = min(self._leeway, token.expires_in / 2)
        return self._clock() + token.expires_in - margin
