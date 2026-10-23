import importlib
import sys
from collections.abc import Callable
from typing import Any


def lazy_exports(
    module_name: str, exports: dict[str, str]
) -> tuple[Callable[[str], Any], Callable[[], list[str]]]:
    """A module __getattr__ and __dir__ that import each exported name on first access.

    exports maps a name to the module that defines it, relative to module_name's package
    (".schemas.repository"). Generated models.py files use this, so a program that uses
    20 of an API's 4,000 models imports 20:

        __getattr__, __dir__ = lazy_exports(__name__, {"Repository": ".schemas.repository"})
    """

    def __getattr__(name: str) -> Any:
        if name not in exports:
            raise AttributeError(f"module {module_name!r} has no attribute {name!r}")
        module = sys.modules[module_name]
        value = getattr(importlib.import_module(exports[name], module.__package__), name)
        setattr(module, name, value)  # later lookups skip __getattr__
        return value

    def __dir__() -> list[str]:
        return sorted({*vars(sys.modules[module_name]), *exports})

    return __getattr__, __dir__
