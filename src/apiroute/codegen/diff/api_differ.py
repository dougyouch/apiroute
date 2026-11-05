from apiroute.codegen.api_definition import ApiDefinition
from apiroute.codegen.diff.api_change import ADDITION, BREAKING, ApiChange
from apiroute.codegen.diff.model_differ import ModelDiffer
from apiroute.codegen.diff.operation_differ import OperationDiffer


class ApiDiffer:
    """What changes in a generated client between two versions of an API description: its
    operations, its models and its webhooks."""

    def __init__(self, old: ApiDefinition, new: ApiDefinition):
        self._old = old
        self._new = new

    def changes(self) -> list[ApiChange]:
        changes = OperationDiffer(self._old, self._new).changes()
        changes += ModelDiffer(self._old, self._new).changes()
        changes += self._webhooks()
        return changes

    def _webhooks(self) -> list[ApiChange]:
        before = {w.wire_name for w in self._old.webhooks}
        after = {w.wire_name for w in self._new.webhooks}
        changes = [ApiChange(BREAKING, f"webhook {n}", "removed") for n in sorted(before - after)]
        changes += [ApiChange(ADDITION, f"webhook {n}", "added") for n in sorted(after - before)]
        return changes
