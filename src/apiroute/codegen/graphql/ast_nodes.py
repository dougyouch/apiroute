import copy
import dataclasses
from typing import Any


def replaced(node: Any, **changes: Any) -> Any:
    """A copy of a graphql-core AST node with changes: graphql-core 3.3's nodes are frozen
    dataclasses, 3.2's plain objects."""
    if dataclasses.is_dataclass(node):
        return dataclasses.replace(node, **changes)
    changed = copy.copy(node)
    for name, value in changes.items():
        setattr(changed, name, value)
    return changed
