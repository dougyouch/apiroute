import re
from collections.abc import Callable
from typing import Any

PLACEHOLDER = re.compile(r"\{([A-Za-z_][A-Za-z0-9_]*)\}")

# ':name' is a parameter unless the colon follows a letter, digit, '_' or '}',
# so items:batchGet, {name}:cancel and 12:30 stay literal
COLON_PARAMETER = re.compile(r"(?<![A-Za-z0-9_}]):([A-Za-z_][A-Za-z0-9_]*)")


class PathTemplate:
    """A route path with {name} (or :name) parameters, filled in and escaped per request."""

    def __init__(self, path: str):
        self.source = path
        normalized = COLON_PARAMETER.sub(r"{\1}", path)
        # re.split with one group alternates literal text and parameter names
        self._parts = tuple(PLACEHOLDER.split(normalized))
        self.names = tuple(dict.fromkeys(self._parts[1::2]))

    def render(self, resolve: Callable[[str], Any], escape: Callable[[Any], str]) -> str:
        return "".join(
            escape(resolve(part)) if index % 2 else part for index, part in enumerate(self._parts)
        )
