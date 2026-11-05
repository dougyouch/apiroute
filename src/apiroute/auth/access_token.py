from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from apiroute.auth.auth_error import AuthError


@dataclass(frozen=True)
class AccessToken:
    """A token from a token endpoint (or wherever a TokenAuthenticator gets one)."""

    value: str
    # Seconds the token is valid for from when it was received; None if it doesn't say
    expires_in: float | None = None
    token_type: str = "Bearer"
    refresh_token: str | None = None
    scope: str | None = None

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
