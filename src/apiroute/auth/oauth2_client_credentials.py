from apiroute.auth.oauth2_token_authenticator import OAuth2TokenAuthenticator


class OAuth2ClientCredentials(OAuth2TokenAuthenticator):
    """The OAuth 2.0 client credentials grant (RFC 6749 section 4.4), for server-to-server
    APIs: the client trades its own ID and secret for an access token, and does so again when
    the token expires or is rejected.

        self.authenticator = OAuth2ClientCredentials(
            "https://auth.example.com/oauth/token", client_id, client_secret,
            scope="orders:read", extra={"audience": "https://api.example.com"},
        )

    The secret is sent in a Basic Authorization header; auth_method="post" sends it as form
    fields instead, for servers that want that.
    """

    def grant(self) -> dict[str, str]:
        return {"grant_type": "client_credentials"}
