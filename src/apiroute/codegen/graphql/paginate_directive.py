from typing import Any

from apiroute.codegen.graphql.ast_nodes import replaced
from apiroute.codegen.graphql.paginate_mark import PaginateMark

NAME = "paginate"


class PaginateDirective:
    """Finds and removes apiroute's client-side @paginate directive. It never reaches
    validation or the server, which don't know it."""

    def strip(self, definition: Any) -> tuple[Any, list[PaginateMark]]:
        """The operation or fragment definition without @paginate, and where it was."""
        marks: list[PaginateMark] = []
        selection_set = self._selection_set(definition.selection_set, (), marks)
        return replaced(definition, selection_set=selection_set), marks

    def _selection_set(self, selection_set: Any, steps: tuple, marks: list) -> Any:
        selections = tuple(self._selection(s, steps, marks) for s in selection_set.selections)
        return replaced(selection_set, selections=selections)

    def _selection(self, selection: Any, steps: tuple, marks: list) -> Any:
        from graphql import FieldNode, FragmentSpreadNode

        if isinstance(selection, FragmentSpreadNode):
            return selection
        changes: dict[str, Any] = {}
        if isinstance(selection, FieldNode):
            here = (*steps, ("field", selection))
            kept = tuple(d for d in selection.directives or () if d.name.value != NAME)
            if len(kept) != len(selection.directives or ()):
                marks.append(PaginateMark(here, selection))
                changes["directives"] = kept
        else:
            condition = selection.type_condition
            here = (*steps, ("on", condition.name.value if condition else None))
        if selection.selection_set is not None:
            changes["selection_set"] = self._selection_set(selection.selection_set, here, marks)
        return replaced(selection, **changes) if changes else selection
