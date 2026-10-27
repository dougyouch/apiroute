from typing import Any

from apiroute.codegen.api_definition import Model, ModelField
from apiroute.codegen.graphql.field_collector import MAYBE, FieldCollector
from apiroute.codegen.graphql.field_entry import FieldEntry
from apiroute.codegen.graphql.graphql_type_mapper import GraphQLTypeMapper, wrap
from apiroute.codegen.python_literals import py_str
from apiroute.codegen.python_names import MODEL_RESERVED, pascal_case, snake_case, unique
from apiroute.codegen.type_ref import TypeRef

TYPENAME = "__typename"


class SelectionModelMapper:
    """Result models shaped by an operation's selections, not by the schema's types: the root
    is <Operation>Result, and each object-valued field gets <Parent><Field>. Fragments are
    flattened into the models that select them. A selection on an interface or union with type
    conditions becomes a union of one model per named type, told apart by __typename, plus a
    fallback (<...>Other) for the types the operation didn't name."""

    def __init__(
        self,
        schema: Any,
        collector: FieldCollector,
        types: GraphQLTypeMapper,
        models: dict[str, Model],
        taken: set[str],
    ):
        self._schema = schema
        self._collector = collector
        self._types = types
        self._models = models
        self._taken = taken

    def result(self, operation: Any, operation_name: str) -> TypeRef:
        """The model for an operation's data (operation is prepared: __typename added)."""
        root = self._schema.get_root_type(operation.operation)
        prefix = pascal_case(operation_name)
        name = self._new_name(f"{prefix}Result")
        entries = self._collector.collect(
            [operation.selection_set], self._collector.for_object(root)
        )
        self._object_model(name, prefix, root, entries)
        return TypeRef.model(name)

    def _object_model(
        self,
        name: str,
        prefix: str,
        parent: Any,
        entries: dict[str, FieldEntry],
        typename: Any = None,
    ) -> None:
        """typename: a type name to fix __typename to (a union member), or "" for any string."""
        model = Model(name)
        self._models[name] = model
        taken: set[str] = set()
        if typename is not None and TYPENAME not in entries:
            model.fields.append(self._typename_field(taken, typename, required=True))
        for entry in entries.values():
            if entry.field_name == TYPENAME:
                fixed = typename if typename is not None else ""
                model.fields.append(
                    self._typename_field(taken, fixed, not entry.conditional, entry.key)
                )
            else:
                model.fields.append(self._field(entry, parent, prefix if prefix else name, taken))

    def _field(self, entry: FieldEntry, parent: Any, prefix: str, taken: set[str]) -> ModelField:
        from graphql import get_named_type, is_leaf_type

        definition = self._definition(entry, parent)
        named = get_named_type(definition.type)
        if is_leaf_type(named):
            leaf = self._types.leaf
        else:
            child = f"{prefix}{pascal_case(entry.key)}"
            leaf = lambda _: self._selection_type(child, named, entry.selection_sets)  # noqa: E731
        python_name = unique(snake_case(entry.key), taken, MODEL_RESERVED)
        return ModelField(
            name=python_name,
            alias=entry.key if python_name != entry.key else None,
            type=wrap(definition.type, leaf),
            required=not entry.conditional,
            description=definition.description or "",
        )

    def _definition(self, entry: FieldEntry, parent: Any) -> Any:
        """The schema field an entry selects: on the model's type when it has it, else on the
        type condition it was selected under (an interface's field, on a union)."""
        fields = getattr(parent, "fields", {})
        if entry.field_name in fields:
            return fields[entry.field_name]
        return self._schema.get_type(entry.scope).fields[entry.field_name]

    def _selection_type(self, base: str, named: Any, selection_sets: list[Any]) -> TypeRef:
        from graphql import is_object_type

        collector = self._collector
        if is_object_type(named):
            name = self._new_name(base)
            entries = collector.collect(selection_sets, collector.for_object(named))
            self._object_model(name, name, named, entries)
            return TypeRef.model(name)
        conditions = collector.type_conditions(selection_sets, named)
        if not conditions:
            name = self._new_name(base)
            entries = collector.collect(selection_sets, collector.for_abstract(named))
            self._object_model(name, name, named, entries)
            return TypeRef.model(name)
        return self._union(base, named, selection_sets, conditions)

    def _union(
        self, base: str, abstract: Any, selection_sets: list[Any], conditions: list[str]
    ) -> TypeRef:
        from graphql import is_object_type

        collector = self._collector
        possible = {t.name: t for t in self._schema.get_possible_types(abstract)}
        named = [possible[c] for c in conditions if c in possible and is_object_type(possible[c])]
        alias = self._new_name(base)
        members = []
        for object_type in named:
            name = self._new_name(f"{base}{pascal_case(object_type.name)}")
            entries = collector.collect(selection_sets, collector.for_object(object_type))
            self._object_model(name, name, object_type, entries, typename=object_type.name)
            members.append(name)
        if len(named) < len(possible):
            name = self._new_name(f"{base}Other")
            entries = collector.collect(selection_sets, collector.for_abstract(abstract, MAYBE))
            self._object_model(name, name, abstract, entries, typename="")
            members.append(name)
        # pydantic's smart union picks the member whose __typename Literal matches (it validates
        # with more fields than the fallback's plain str); union_mode isn't in pydantic 2.0
        expr = " | ".join(members)
        self._models[alias] = Model(alias, alias_of=TypeRef(expr, frozenset(members)))
        return TypeRef.model(alias)

    def _typename_field(
        self, taken: set[str], typename: str, required: bool, key: str = TYPENAME
    ) -> ModelField:
        python_name = unique(snake_case(key), taken, MODEL_RESERVED)
        field_type = TypeRef(f"Literal[{py_str(typename)}]") if typename else TypeRef("str")
        return ModelField(python_name, key if python_name != key else None, field_type, required)

    def _new_name(self, name: str) -> str:
        return unique(name, self._taken, frozenset())
