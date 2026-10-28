import re
from collections.abc import Iterable

# Built-in types generated annotations use, which a generated method can shadow
BUILTIN_TYPES = frozenset(
    {"bool", "bytes", "dict", "float", "frozenset", "int", "list", "object", "set", "str", "tuple"}
)

_STRING = re.compile(r"(\"(?:\\.|[^\"\\])*\"|'(?:\\.|[^'\\])*')")


class BuiltinShadowing:
    """Annotations in a class whose methods are named like built-in types: inside a class
    with a method `list` (GitHub's gists.list), a later `list[Gist]` names that method to a
    type checker, so such annotations say builtins.list instead. Text in quotes is left as is,
    and `used` says whether the module needs `import builtins`."""

    def __init__(self, method_names: Iterable[str]):
        shadowed = sorted(BUILTIN_TYPES.intersection(method_names))
        self._pattern = re.compile(rf"(?<![\w.])({'|'.join(shadowed)})\b") if shadowed else None
        self.used = False

    def qualified(self, annotation: str) -> str:
        if self._pattern is None:
            return annotation
        parts = _STRING.split(annotation)  # odd indexes are the quoted strings
        for index in range(0, len(parts), 2):
            parts[index] = self._pattern.sub(r"builtins.\1", parts[index])
        result = "".join(parts)
        self.used = self.used or result != annotation
        return result
