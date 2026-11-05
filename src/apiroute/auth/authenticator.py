from typing import Any

from apiroute.request_spec import RequestSpec
from apiroute.unexpected_response import UnexpectedResponse

UNAUTHORIZED = 401


class Authenticator:
    """Base class for credentials that change while a client is in use, such as OAuth access
    tokens that expire. Set an instance as the client's `authenticator`:

        class Api(Client):
            def __init__(self, client_id, client_secret, **kwargs):
                super().__init__(**kwargs)
                self.authenticator = OAuth2ClientCredentials(TOKEN_URL, client_id, client_secret)

    Before each attempt, the client asks for the current credential and applies it to the
    request. When the attempt fails with an error that rejects() the credential (by default a
    401), the client invalidates that credential, asks for a fresh one and sends the request
    once more; that resend doesn't count as a retry.

    Subclasses implement credential() and apply(), and invalidate() if they cache. Fetching may
    block, so async calls go through acredential(), which by default calls credential().
    """

    def credential(self, client: Any) -> Any:
        """The credential to send now, fetched or refreshed first if needed. `client` is the
        API client making the call, whose transports a token request can use."""
        raise NotImplementedError

    async def acredential(self, client: Any) -> Any:
        """credential() for async calls; override when fetching does I/O."""
        return self.credential(client)

    def apply(self, request: RequestSpec, credential: Any) -> RequestSpec:
        """The request carrying the credential, e.g. with an Authorization header."""
        raise NotImplementedError

    def rejects(self, error: Exception) -> bool:
        """Whether an attempt's error says the credential is no longer accepted: by default an
        UnexpectedResponse with status 401. Override for APIs that report an expired token
        another way (raise your own exception from check_response, and recognise it here)."""
        return isinstance(error, UnexpectedResponse) and error.status_code == UNAUTHORIZED

    def invalidate(self, credential: Any) -> None:
        """Forgets a rejected credential, so the next credential() call fetches another. It is
        given the credential that was rejected: when another call has already replaced it, the
        newer one is kept."""
