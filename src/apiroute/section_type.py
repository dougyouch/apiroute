from typing import Any, TypeVar, overload

S = TypeVar("S")


class SectionType(type):
    """Section's metaclass, for type checkers only: a Section class nested in a client is
    reached as an instance (client.issues), since the router replaces it with an accessor
    when the client class is created. pyright follows this __get__; mypy doesn't, and sees
    such a section's routes as Any.

    At run time it only runs for a Section class kept on a class that isn't a client or
    section, and returns the class, as attribute access always did."""

    @overload
    def __get__(cls: type[S], instance: None, owner: type) -> type[S]: ...  # type: ignore[misc]

    @overload
    def __get__(cls: type[S], instance: object, owner: type) -> S: ...  # type: ignore[misc]

    def __get__(cls, instance: Any, owner: type) -> Any:
        return cls
