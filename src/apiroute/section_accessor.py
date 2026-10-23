from typing import Any


class SectionAccessor:
    """Replaces a nested Section class: client.issues is that section, bound to the client.

    The instance is cached on the client, and the class stays reachable as Client.issues.
    """

    def __init__(self, name: str, section_class: type):
        self._name = name
        self.section_class = section_class

    def __get__(self, instance: Any, owner: type) -> Any:
        if instance is None:
            return self.section_class
        section = self.section_class(instance)
        instance.__dict__[self._name] = section
        return section

    @classmethod
    def install(cls, router_class: type) -> None:
        for name, value in list(vars(router_class).items()):
            if isinstance(value, type) and getattr(value, "_is_section", False):
                setattr(router_class, name, cls(name, value))
