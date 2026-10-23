import importlib
import sys
from typing import Any


class LazyAttribute:
    """A section or .models view kept in another module, imported on first access and
    cached on the instance, so a client with thousands of routes loads only what it uses.

        class GitHubApi(Client):
            issues = lazy(".issues.client", "IssuesSection")
            models = lazy(".models.client", "GitHubApiModels")

    The module path is relative to the package of the module that defines the class.
    Reading the attribute on the class returns the class it names.
    """

    def __init__(self, module: str, class_name: str):
        self._module = module
        self._class_name = class_name
        self._name: str | None = None
        self._package: str | None = None

    def __set_name__(self, owner: type, name: str) -> None:
        self._name = name
        self._package = sys.modules[owner.__module__].__package__

    def load(self) -> type:
        module = importlib.import_module(self._module, self._package)
        return getattr(module, self._class_name)

    def __get__(self, instance: Any, owner: type) -> Any:
        if instance is None:
            return self.load()
        value = self.load()(instance)
        instance.__dict__[self._name] = value
        return value


def lazy(module: str, class_name: str) -> Any:
    return LazyAttribute(module, class_name)
