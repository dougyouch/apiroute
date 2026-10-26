import re
from urllib.parse import unquote, urlsplit, urlunsplit

MASK = "***"

# Words that mark a query parameter as a secret: a name containing one as a whole word
# ("api_key", "accessToken", "client-secret") has its value masked
SECRET_WORDS = frozenset(
    {
        "apikey",
        "auth",
        "credential",
        "credentials",
        "jwt",
        "key",
        "passwd",
        "password",
        "pwd",
        "secret",
        "session",
        "sig",
        "signature",
        "token",
    }
)

_WORD = re.compile(r"[A-Z]?[a-z0-9]+|[A-Z]+(?![a-z])")


class UrlRedactor:
    """Masks the secrets in a URL so it can go into an error message or a log line.

    Masks the value of every query parameter whose name contains a secret word, and the
    password in the URL's userinfo. Everything else is kept as written. A key carried in the
    path (some providers put it there) can't be recognised by name; override
    Client.redact_url for that.
    """

    def __init__(self, secret_words: frozenset[str] = SECRET_WORDS):
        self._secret_words = secret_words

    def redact(self, url: str) -> str:
        parts = urlsplit(url)
        netloc = self._redact_userinfo(parts.netloc)
        query = "&".join(self._redact_pair(pair) for pair in parts.query.split("&"))
        return urlunsplit((parts.scheme, netloc, parts.path, query, parts.fragment))

    def is_secret(self, name: str) -> bool:
        words = [word.lower() for word in _WORD.findall(name)]
        joined = "".join(words)
        return joined in self._secret_words or any(word in self._secret_words for word in words)

    def _redact_pair(self, pair: str) -> str:
        name, sep, _ = pair.partition("=")
        return f"{name}={MASK}" if sep and self.is_secret(unquote(name)) else pair

    @staticmethod
    def _redact_userinfo(netloc: str) -> str:
        userinfo, at, host = netloc.rpartition("@")
        if not at or ":" not in userinfo:
            return netloc
        user = userinfo.split(":", 1)[0]
        return f"{user}:{MASK}@{host}"
