from collections.abc import Iterable


def signing_keys(secret: str | bytes | Iterable[str | bytes]) -> list[bytes]:
    """The secret, or each of several (while one is being rotated out), as bytes."""
    secrets = [secret] if isinstance(secret, (str, bytes)) else list(secret)
    if not secrets:
        raise ValueError("a webhook signature needs at least one secret")
    return [s.encode() if isinstance(s, str) else bytes(s) for s in secrets]
