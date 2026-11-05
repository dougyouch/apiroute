import re

from apiroute.codegen.api_definition import ApiDefinition, Operation, Parameter
from apiroute.codegen.diff.api_change import ADDITION, BREAKING, ApiChange
from apiroute.codegen.diff.type_change import type_change

_PATH_PARAMETER = re.compile(r"\{[^}]*\}")


class OperationDiffer:
    """Compares operations, matched by method and path as the spec writes them (path
    parameter names aside, since renaming one changes no URL)."""

    def __init__(self, old: ApiDefinition, new: ApiDefinition):
        self._old = _operations(old)
        self._new = _operations(new)

    def changes(self) -> list[ApiChange]:
        changes = []
        for key in sorted(self._old.keys() - self._new.keys()):
            changes.append(ApiChange(BREAKING, key, f"removed ({self._old[key][0]})"))
        for key in sorted(self._new.keys() - self._old.keys()):
            changes.append(ApiChange(ADDITION, key, f"added ({self._new[key][0]})"))
        for key in sorted(self._old.keys() & self._new.keys()):
            changes += self._compared(key, self._old[key], self._new[key])
        return changes

    def _compared(
        self, key: str, old: tuple[str, Operation], new: tuple[str, Operation]
    ) -> list[ApiChange]:
        (old_name, old_op), (new_name, new_op) = old, new
        changes = []
        if old_name != new_name:
            changes.append(ApiChange(BREAKING, key, f"method renamed {old_name} -> {new_name}"))
        changes += _parameters(key, old_op.parameters, new_op.parameters)
        changes += _body(key, old_op, new_op)
        old_response = old_op.response.expr if old_op.response else old_op.response_plain
        new_response = new_op.response.expr if new_op.response else new_op.response_plain
        kind = type_change(old_response, new_response)
        if kind is not None:
            changes.append(ApiChange(kind, key, f"response {old_response} -> {new_response}"))
        return changes


def _operations(definition: ApiDefinition) -> dict[str, tuple[str, Operation]]:
    """Route key -> (the method's dotted name on the client, the operation)."""
    found = {}
    for group in [definition.root, *definition.groups]:
        for operation in group.operations:
            dotted = f"{group.name}.{operation.name}" if group.name else operation.name
            method, _, path = (operation.spec_route or f"{operation.method} ").partition(" ")
            found[f"{method} {_PATH_PARAMETER.sub('{}', path)}"] = (dotted, operation)
    return found


def _parameters(key: str, old: list[Parameter], new: list[Parameter]) -> list[ApiChange]:
    before = {(p.location, p.wire_name): p for p in old}
    after = {(p.location, p.wire_name): p for p in new}
    changes = []
    for where, parameter in sorted(before.items()):
        label = f"{parameter.location} parameter {parameter.wire_name}"
        if where not in after:
            changes.append(ApiChange(BREAKING, key, f"{label} removed"))
            continue
        changed = after[where]
        if changed.required and not parameter.required:
            changes.append(ApiChange(BREAKING, key, f"{label} is now required"))
        kind = type_change(parameter.type.expr, changed.type.expr)
        if kind is not None:
            detail = f"{label} type {parameter.type.expr} -> {changed.type.expr}"
            changes.append(ApiChange(kind, key, detail))
    for where, parameter in sorted(after.items()):
        if where not in before:
            label = f"{parameter.location} parameter {parameter.wire_name}"
            kind = BREAKING if parameter.required else ADDITION
            detail = "added, required" if parameter.required else "added"
            changes.append(ApiChange(kind, key, f"{label} {detail}"))
    return changes


def _body(key: str, old: Operation, new: Operation) -> list[ApiChange]:
    if old.body is None and new.body is None:
        return []
    if new.body is None:
        return [ApiChange(BREAKING, key, "request body removed")]
    if old.body is None:
        kind = BREAKING if new.body.required else ADDITION
        return [
            ApiChange(kind, key, "request body added" + (", required" if new.body.required else ""))
        ]
    changes = []
    if new.body.required and not old.body.required:
        changes.append(ApiChange(BREAKING, key, "request body is now required"))
    if old.body.body_format != new.body.body_format:
        detail = f"request body format {old.body.body_format} -> {new.body.body_format}"
        changes.append(ApiChange(BREAKING, key, detail))
    retyped = type_change(old.body.type.expr, new.body.type.expr)
    if retyped is not None:
        detail = f"request body {old.body.type.expr} -> {new.body.type.expr}"
        changes.append(ApiChange(retyped, key, detail))
    return changes
