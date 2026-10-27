from typing import Any

from apiroute.codegen.graphql.ast_nodes import replaced
from apiroute.codegen.graphql.field_collector import FieldCollector


class TypenameInserter:
    """Adds __typename to each selection set on an interface or union that has type
    conditions and doesn't select it already, so result models can tell the types apart.
    Returns changed copies; the parsed nodes (which validation reports against) stay as read."""

    def __init__(self, schema: Any, collector: FieldCollector):
        self._schema = schema
        self._collector = collector

    def definition(self, node: Any) -> Any:
        """An operation or fragment definition, with __typename added where needed."""
        from graphql import FragmentDefinitionNode

        if isinstance(node, FragmentDefinitionNode):
            parent = self._schema.get_type(node.type_condition.name.value)
        else:
            parent = self._schema.get_root_type(node.operation)
        return _with_selection_set(node, self._selection_set(node.selection_set, parent))

    def _selection_set(self, selection_set: Any, parent: Any) -> Any:
        from graphql import FieldNode, NameNode, is_abstract_type

        selections = [self._selection(selection, parent) for selection in selection_set.selections]
        if (
            parent is not None
            and is_abstract_type(parent)
            and self._collector.type_conditions([selection_set], parent)
            and not any(_is_typename(selection) for selection in selections)
        ):
            typename = FieldNode(name=NameNode(value="__typename"), arguments=(), directives=())
            selections.insert(0, typename)
        return replaced(selection_set, selections=tuple(selections))

    def _selection(self, selection: Any, parent: Any) -> Any:
        from graphql import FieldNode, FragmentSpreadNode, get_named_type

        if isinstance(selection, FragmentSpreadNode) or selection.selection_set is None:
            return selection
        if isinstance(selection, FieldNode):
            field = getattr(parent, "fields", {}).get(selection.name.value)
            inner_parent = get_named_type(field.type) if field is not None else None
        elif selection.type_condition is not None:
            inner_parent = self._schema.get_type(selection.type_condition.name.value)
        else:
            inner_parent = parent
        return _with_selection_set(
            selection, self._selection_set(selection.selection_set, inner_parent)
        )


def _with_selection_set(node: Any, selection_set: Any) -> Any:
    return replaced(node, selection_set=selection_set)


def _is_typename(selection: Any) -> bool:
    from graphql import FieldNode

    return (
        isinstance(selection, FieldNode)
        and selection.name.value == "__typename"
        and selection.alias is None
    )
