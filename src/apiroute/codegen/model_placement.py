from apiroute.codegen.api_definition import ApiDefinition, Group, Operation

ROOT = ""


class ModelPlacement:
    """Decides which models/models.py each model is written to.

    A model used only by one tag's operations (directly or through other models) lives in
    that tag's folder; one used by the root or by several tags, or referenced by a model
    that lives at the root, lives at the root. Tag folders may import root models, never
    the other way round.
    """

    def __init__(self, definition: ApiDefinition):
        self._definition = definition

    def place(self) -> dict[str, str]:
        """Model name -> group name ("" for the root)."""
        users = self._users()
        placement = {
            name: next(iter(groups)) if len(groups) == 1 else ROOT for name, groups in users.items()
        }
        self._pull_dependencies_to_root(placement)
        return placement

    def _users(self) -> dict[str, set[str]]:
        users: dict[str, set[str]] = {name: set() for name in self._definition.models}
        for group in [self._definition.root, *self._definition.groups]:
            for name in self._closure(self._direct_models(group)):
                users[name].add(group.name)
        for groups in users.values():
            if not groups:
                groups.add(ROOT)  # declared by the spec but used by no operation
        return users

    def _direct_models(self, group: Group) -> set[str]:
        names: set[str] = set()
        for operation in group.operations:
            names |= operation_models(operation)
        return names

    def _closure(self, names: set[str]) -> set[str]:
        seen: set[str] = set()
        pending = list(names)
        while pending:
            name = pending.pop()
            if name in seen or name not in self._definition.models:
                continue
            seen.add(name)
            pending.extend(self._dependencies(name))
        return seen

    def _dependencies(self, name: str) -> set[str]:
        model = self._definition.models[name]
        if model.alias_of is not None:
            return set(model.alias_of.models)
        return {dep for field in model.fields for dep in field.type.models}

    def _pull_dependencies_to_root(self, placement: dict[str, str]) -> None:
        changed = True
        while changed:
            changed = False
            for name, group in list(placement.items()):
                if group != ROOT:
                    continue
                for dependency in self._dependencies(name):
                    if placement.get(dependency, ROOT) != ROOT:
                        placement[dependency] = ROOT
                        changed = True


def operation_models(operation: Operation) -> set[str]:
    names: set[str] = set()
    for parameter in operation.parameters:
        names |= parameter.type.models
    if operation.body is not None:
        names |= operation.body.type.models
    if operation.response is not None:
        names |= operation.response.models
    return names
