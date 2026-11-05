"""Credentials that change while a client is in use: OAuth 2.0 tokens and your own.

Names are imported on first use: the OAuth classes build on Client, which the route executor
behind every Client imports this package's attempt runner for.
"""

from typing import TYPE_CHECKING

from apiroute.lazy_exports import lazy_exports

if TYPE_CHECKING:
    from apiroute.auth.access_token import AccessToken
    from apiroute.auth.auth_error import AuthError
    from apiroute.auth.authenticator import Authenticator
    from apiroute.auth.oauth2_client_credentials import OAuth2ClientCredentials
    from apiroute.auth.oauth2_refresh_token import OAuth2RefreshToken
    from apiroute.auth.oauth2_token_authenticator import OAuth2TokenAuthenticator
    from apiroute.auth.token_authenticator import TokenAuthenticator

__all__ = [
    "AccessToken",
    "AuthError",
    "Authenticator",
    "OAuth2ClientCredentials",
    "OAuth2RefreshToken",
    "OAuth2TokenAuthenticator",
    "TokenAuthenticator",
]

__getattr__, __dir__ = lazy_exports(
    __name__,
    {
        "AccessToken": ".access_token",
        "AuthError": ".auth_error",
        "Authenticator": ".authenticator",
        "OAuth2ClientCredentials": ".oauth2_client_credentials",
        "OAuth2RefreshToken": ".oauth2_refresh_token",
        "OAuth2TokenAuthenticator": ".oauth2_token_authenticator",
        "TokenAuthenticator": ".token_authenticator",
    },
)
