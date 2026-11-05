from apiroute.codegen.api_definition import ApiDefinition, Model, ModelField
from apiroute.codegen.diff.api_change import ADDITION, BREAKING, ApiChange
from apiroute.codegen.diff.model_usage import ModelUsage
from apiroute.codegen.diff.type_change import type_change


class ModelDiffer:
    """Compares the models by name. A field is matched by its wire name. Whether a change
    breaks depends on the side: a client receiving a model breaks when a field it relied on is
    removed, changes type or may be missing; one sending it, when a field becomes required."""

    def __init__(self, old: ApiDefinition, new: ApiDefinition):
        self._old = old.models
        self._new = new.models
        self._usage = ModelUsage(new)
        self._old_usage = ModelUsage(old)

    def changes(self) -> list[ApiChange]:
        changes = []
        for name in sorted(self._old.keys() - self._new.keys()):
            changes.append(ApiChange(BREAKING, f"model {name}", "removed"))
        for name in sorted(self._new.keys() - self._old.keys()):
            changes.append(ApiChange(ADDITION, f"model {name}", "added"))
        for name in sorted(self._old.keys() & self._new.keys()):
            changes += self._compared(self._old[name], self._new[name])
        return changes

    def _compared(self, old: Model, new: Model) -> list[ApiChange]:
        if old.alias_of is not None or new.alias_of is not None:
            old_expr = old.alias_of.expr if old.alias_of else "a model"
            new_expr = new.alias_of.expr if new.alias_of else "a model"
            kind = type_change(old_expr, new_expr)
            return (
                []
                if kind is None
                else [ApiChange(kind, f"model {old.name}", f"{old_expr} -> {new_expr}")]
            )
        sent = old.name in self._usage.sent | self._old_usage.sent
        received = old.name in self._usage.received | self._old_usage.received
        before = {_wire(f): f for f in old.fields}
        after = {_wire(f): f for f in new.fields}
        changes = []
        for wire, field in before.items():
            subject = f"{old.name}.{wire}"
            if wire not in after:
                changes.append(ApiChange(BREAKING, subject, "removed"))
            else:
                changes += _field(subject, field, after[wire], sent, received)
        for wire, field in after.items():
            if wire not in before:
                breaks = sent and field.required
                detail = "added, required" if field.required else "added"
                changes.append(
                    ApiChange(BREAKING if breaks else ADDITION, f"{old.name}.{wire}", detail)
                )
        return changes


def _field(
    subject: str, old: ModelField, new: ModelField, sent: bool, received: bool
) -> list[ApiChange]:
    changes = []
    if old.required and not new.required:
        kind = BREAKING if received else ADDITION
        changes.append(ApiChange(kind, subject, "now optional"))
    if new.required and not old.required:
        kind = BREAKING if sent else ADDITION
        changes.append(ApiChange(kind, subject, "now required"))
    retyped = type_change(old.type.expr, new.type.expr)
    if retyped is not None:
        changes.append(ApiChange(retyped, subject, f"type {old.type.expr} -> {new.type.expr}"))
    return changes


def _wire(field: ModelField) -> str:
    return field.alias or field.name
