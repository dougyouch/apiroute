from collections.abc import Callable
from typing import Any

from apiroute.codegen.graphql.field_entry import FieldEntry

ALWAYS, MAYBE, NEVER = "always", "maybe", "never"

# Whether the fields under a type condition (None: no condition) apply to the type being
# modelled: always, maybe (the response may or may not include them) or never
Applies = Callable[[str | None], str]


class FieldCollector:
    """Flattens selection sets (fields, inline fragments, fragment spreads) into the response
    keys a model needs, following GraphQL's field collection."""

    def __init__(self, schema: Any, fragments: dict[str, Any]):
        self._schema = schema
        self._fragments = fragments

    def collect(self, selection_sets: list[Any], applies: Applies) -> dict[str, FieldEntry]:
        entries: dict[str, FieldEntry] = {}
        for selection_set in selection_sets:
            self._walk(selection_set, applies, False, entries, None)
        return entries

    def for_object(self, object_type: Any) -> Applies:
        """Conditions met by a concrete type: none, the type itself, or an abstract type it
        belongs to."""

        def applies(condition: str | None) -> str:
            if condition is None or condition == object_type.name:
                return ALWAYS
            condition_type = self._schema.get_type(condition)
            if self._is_abstract(condition_type) and self._schema.is_sub_type(
                condition_type, object_type
            ):
                return ALWAYS
            return NEVER

        return applies

    def for_abstract(self, abstract_type: Any, others: str = NEVER) -> Applies:
        """The fields an interface or union shares: no condition or its own; other conditions
        on abstract types count as others (the fallback model takes them as optional)."""

        def applies(condition: str | None) -> str:
            if condition is None or condition == abstract_type.name:
                return ALWAYS
            return others if self._is_abstract(self._schema.get_type(condition)) else NEVER

        return applies

    def type_conditions(self, selection_sets: list[Any], parent: Any) -> list[str]:
        """The type conditions (other than parent itself) in these selection sets, in order."""
        found: list[str] = []
        for selection_set in selection_sets:
            self._conditions(selection_set, parent.name, found)
        return found

    def _walk(
        self, selection_set: Any, applies: Applies, conditional: bool, entries: dict, scope: Any
    ) -> None:
        from graphql import FieldNode, FragmentSpreadNode

        for selection in selection_set.selections:
            optional = conditional or _has_condition_directive(selection)
            if isinstance(selection, FieldNode):
                _add(entries, selection, optional, scope)
                continue
            if isinstance(selection, FragmentSpreadNode):
                fragment = self._fragments.get(selection.name.value)
                if fragment is None:
                    continue
                condition, inner = fragment.type_condition.name.value, fragment.selection_set
            else:
                condition = (
                    selection.type_condition.name.value if selection.type_condition else None
                )
                inner = selection.selection_set
            verdict = applies(condition)
            if verdict != NEVER:
                inner_scope = condition or scope
                self._walk(inner, applies, optional or verdict == MAYBE, entries, inner_scope)

    def _conditions(self, selection_set: Any, parent_name: str, found: list[str]) -> None:
        from graphql import FieldNode, FragmentSpreadNode

        for selection in selection_set.selections:
            if isinstance(selection, FieldNode):
                continue
            if isinstance(selection, FragmentSpreadNode):
                fragment = self._fragments.get(selection.name.value)
                if fragment is None:
                    continue
                condition, inner = fragment.type_condition.name.value, fragment.selection_set
            else:
                condition = (
                    selection.type_condition.name.value if selection.type_condition else None
                )
                inner = selection.selection_set
            if condition is not None and condition != parent_name and condition not in found:
                found.append(condition)
            if condition is None or condition == parent_name:
                self._conditions(inner, parent_name, found)

    @staticmethod
    def _is_abstract(graphql_type: Any) -> bool:
        from graphql import is_abstract_type

        return graphql_type is not None and is_abstract_type(graphql_type)


def _add(entries: dict[str, FieldEntry], node: Any, conditional: bool, scope: Any) -> None:
    key = node.alias.value if node.alias else node.name.value
    current = entries.get(key)
    if current is None:
        entries[key] = FieldEntry(key, node.name.value, (node,), conditional, scope)
    else:
        # selected again: the sub-selections merge, and it's optional only if every one is
        entries[key] = current._replace(
            nodes=(*current.nodes, node), conditional=current.conditional and conditional
        )


def _has_condition_directive(selection: Any) -> bool:
    return any(d.name.value in ("include", "skip") for d in selection.directives or ())
