import json
from pathlib import Path

from apiroute.codegen.api_definition import ApiDefinition, Group, Operation
from apiroute.codegen.python_names import RESERVED, pascal_case, snake_case


class OperationNames:
    """Renames and regroups operations from a map of the spec's operation IDs to dotted names
    (--operation-names), for a spec whose tags and operationIds make poor sections and
    methods:

        {"PostCustomers": "customers.create", "GetIssuingCards": "issuing.cards.list"}

    An operation can also be keyed by its method and path as the spec writes them
    ("GET /api/data/metar"), which names operations that have no operationId.

    The last part is the method; the parts before it are sections, nested, created as needed.
    A name without a dot puts the method on the root client. Operations the map doesn't name
    stay where the spec put them, and names in the map that match no operation are warnings.
    """

    def __init__(self, names: dict[str, str]):
        self._names = names

    @classmethod
    def load(cls, path: str) -> "OperationNames":
        names = json.loads(Path(path).read_text())
        if not isinstance(names, dict) or not all(
            isinstance(key, str) and isinstance(value, str) for key, value in names.items()
        ):
            raise ValueError(f"{path}: expected a JSON object of operation IDs to dotted names")
        return cls(names)

    def apply(self, definition: ApiDefinition) -> None:
        groups = {group.name: group for group in [definition.root, *definition.groups]}
        found = set()
        for group in list(groups.values()):
            for operation in list(group.operations):
                key = self._key(operation)
                if key is None:
                    continue
                found.add(key)
                dotted = self._names[key]
                section, method = _split(dotted)
                group.operations.remove(operation)
                operation.name = method
                _group(groups, section).operations.append(operation)
        definition.warnings += [
            f"--operation-names: no operation {key!r}" for key in self._names if key not in found
        ]
        _check(groups)
        definition.groups = [
            group
            for name, group in sorted(groups.items())
            if name and (group.operations or _has_children(groups, name))
        ]

    def _key(self, operation: Operation) -> str | None:
        """The map's key for operation: its operation ID, or else its method and path."""
        for key in (operation.operation_id, operation.spec_route):
            if key and key in self._names:
                return key
        return None


def _split(dotted: str) -> tuple[str, str]:
    parts = [snake_case(part) for part in dotted.split(".")]
    return ".".join(parts[:-1]), parts[-1]


def _group(groups: dict[str, Group], name: str) -> Group:
    """The section named name, creating it and the sections above it as needed."""
    if name not in groups:
        if "." in name:
            _group(groups, name.rsplit(".", 1)[0])
        groups[name] = Group(name, f"{pascal_case(name.replace('.', '_'))}Section")
    return groups[name]


def _has_children(groups: dict[str, Group], name: str) -> bool:
    return any(other.startswith(f"{name}.") and groups[other].operations for other in groups)


def _check(groups: dict[str, Group]) -> None:
    """Each section's attributes, its methods and child sections, must be distinct names."""
    problems = []
    for name, group in groups.items():
        children = {child.rsplit(".", 1)[-1] for child in groups if _parent(child) == name}
        seen: dict[str, Operation] = {}
        for operation in group.operations:
            where = f"{name}.{operation.name}" if name else operation.name
            if operation.name in seen:
                problems.append(
                    f"{where}: both {_spec_name(seen[operation.name])} and {_spec_name(operation)}"
                )
            elif operation.name in children:
                problems.append(f"{where}: {_spec_name(operation)} has a section's name")
            elif operation.name in RESERVED:
                problems.append(f"{where}: {_spec_name(operation)} has a reserved name")
            seen[operation.name] = operation
    if problems:
        raise ValueError("--operation-names: " + "; ".join(problems))


def _spec_name(operation: Operation) -> str:
    return operation.operation_id or operation.spec_route


def _parent(name: str) -> str | None:
    if not name:
        return None
    return name.rsplit(".", 1)[0] if "." in name else ""
