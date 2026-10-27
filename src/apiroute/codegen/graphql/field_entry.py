from typing import Any, NamedTuple


class FieldEntry(NamedTuple):
    """One response key of a selection: the schema field it selects, every node selecting it
    (GraphQL merges their sub-selections), whether the response may leave it out, and the type
    condition it was selected under (None: the model's own type), where the field is defined."""

    key: str
    field_name: str
    nodes: tuple[Any, ...]
    conditional: bool
    scope: str | None = None

    @property
    def selection_sets(self) -> list[Any]:
        return [node.selection_set for node in self.nodes if node.selection_set is not None]
