import threading
from collections.abc import Iterator
from contextlib import contextmanager

# Per thread, like the Ruby gem's, so classes defined on two threads at once don't mix
_state = threading.local()


@contextmanager
def namespace(prefix: str) -> Iterator[None]:
    """Prefixes the path of every route declared inside the block, as the gem's namespace does:

        class Api(Client):
            with namespace("/admin"):
                list_users = route("/users")   # GET /admin/users

    Blocks nest, joining their prefixes in order.
    """
    stack = _stack()
    stack.append(prefix)
    try:
        yield
    finally:
        stack.pop()


def current_prefix() -> str:
    return "".join(_stack())


def _stack() -> list[str]:
    if not hasattr(_state, "prefixes"):
        _state.prefixes = []
    return _state.prefixes
