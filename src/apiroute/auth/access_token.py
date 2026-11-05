from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from apiroute.auth.auth_error import AuthError


@dataclass(frozen=True)
class AccessToken:
    """A token from a token endpoint (or wherever a TokenAuthenticator gets one).

    Its lifetime is given as expires_in (seconds from when it was received, as OAuth replies
    say) or expires_at (a Unix time, as many other token APIs and a JWT's exp say), not both.
    """

    value: str
    # Seconds the token is valid for from when it was received; None if it doesn't say
    expires_in: float | None = None
    token_type: str = "Bearer"
    refresh_token: str | None = None
    scope: str | None = None
    # The Unix time (seconds) the token expires at; None if it doesn't say
    expires_at: float | None = None

    def __post_init__(self) -> None:
        if self.expires_in is not None and self.expires_at is not None:
            raise ValueError("an AccessToken takes expires_in or expires_at, not both")

    def lifetime(self, now: float) -> float | None:
        """Seconds the token is valid for, given the Unix time now; None if it doesn't say."""
        if self.expires_at is not None:
            return self.expires_at - now
        return self.expires_in

    @classmethod
    def from_reply(cls, reply: Any) -> "AccessToken":
        """Reads an OAuth 2.0 token response (RFC 6749 section 5.1). expires_in may be a number
        or numeric text, as some providers send it."""
        if not isinstance(reply, Mapping) or not isinstance(reply.get("access_token"), str):
            raise AuthError("the token endpoint's reply has no access_token")
        return cls(
            value=reply["access_token"],
            expires_in=_seconds(reply.get("expires_in")),
            token_type=_scheme(reply.get("token_type")),
            refresh_token=reply.get("refresh_token"),
            scope=reply.get("scope"),
        )

    @property
    def authorization(self) -> str:
        """The Authorization header value, e.g. "Bearer abc"."""
        return f"{self.token_type} {self.value}"


def _seconds(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        raise AuthError(f"the token endpoint's expires_in isn't a number: {value!r}") from None


def _scheme(value: Any) -> str:
    """The token type as an Authorization scheme. Servers often send "bearer", which some APIs
    refuse in the header, so it is sent as "Bearer"."""
    if not value:
        return "Bearer"
    return "Bearer" if str(value).lower() == "bearer" else str(value)
