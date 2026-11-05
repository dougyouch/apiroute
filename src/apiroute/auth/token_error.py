from typing import Any

from apiroute.auth.auth_error import AuthError
from apiroute.unexpected_response import UnexpectedResponse


def token_error(error: UnexpectedResponse) -> AuthError:
    """An AuthError for a token endpoint's refusal, with its OAuth error code and description
    (RFC 6749 section 5.2) when the body has them. It never carries the request's form, which
    holds the client secret or refresh token."""
    code, description = _oauth_error(error)
    detail = f": {code}" if code else ""
    if description:
        detail += f" ({description})"
    return AuthError(
        f"token request failed with status {error.status_code}{detail}",
        response=error.response,
        error=code,
        description=description,
    )


def _oauth_error(error: UnexpectedResponse) -> tuple[str | None, str | None]:
    try:
        body: Any = error.response.json()
    except ValueError:
        return None, None
    if not isinstance(body, dict):
        return None, None
    code, description = body.get("error"), body.get("error_description")
    return (
        code if isinstance(code, str) else None,
        description if isinstance(description, str) else None,
    )
