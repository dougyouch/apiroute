from typing import Any

from apiroute.codegen.api_definition import Model, ModelField
from apiroute.codegen.python_literals import py_str
from apiroute.codegen.python_names import MODEL_RESERVED, pascal_case, snake_case, unique
from apiroute.codegen.type_ref import ANY, TypeRef

BUILTIN_SCALARS = {"Int": "int", "Float": "float", "String": "str", "ID": "str", "Boolean": "bool"}


class GraphQLTypeMapper:
    """Python types for a schema's leaf and input types: built-in scalars, custom scalars (Any,
    or the type --scalar maps them to), enums as Literal aliases and input objects as models.
    Models are added to `models` the first time a type is used, so only reachable ones exist."""

    def __init__(
        self, models: dict[str, Model], taken: set[str], scalars: dict[str, tuple[str, str]]
    ):
        self._models = models
        self._taken = taken
        self._scalars = scalars
        self._names: dict[str, str] = {}  # schema type name -> model name

    def leaf(self, named: Any) -> TypeRef:
        """A scalar's or an enum's type."""
        from graphql import is_enum_type

        if is_enum_type(named):
            return self._enum(named)
        if named.name in BUILTIN_SCALARS:
            return TypeRef(BUILTIN_SCALARS[named.name])
        if named.name in self._scalars:
            return self._mapped_scalar(named)
        return ANY

    def input(self, graphql_type: Any) -> TypeRef:
        """A variable's or input field's type, nullable as the schema says."""
        return wrap(graphql_type, self._input_leaf)

    def required_input(self, graphql_type: Any) -> TypeRef:
        """A variable's type without its outer nullability (a parameter's | None comes from
        being optional)."""
        from graphql import GraphQLNonNull, get_nullable_type

        return wrap(GraphQLNonNull(get_nullable_type(graphql_type)), self._input_leaf)

    def _input_leaf(self, named: Any) -> TypeRef:
        from graphql import is_input_object_type

        if is_input_object_type(named):
            return self._input_object(named)
        return self.leaf(named)

    def _enum(self, named: Any) -> TypeRef:
        name = self._name(named.name)
        if name not in self._models:
            values = ", ".join(py_str(value) for value in named.values)
            alias = TypeRef(f"Literal[{values}]")
            self._models[name] = Model(name, description=named.description or "", alias_of=alias)
        return TypeRef.model(name)

    def _mapped_scalar(self, named: Any) -> TypeRef:
        name = self._name(named.name)
        if name not in self._models:
            module, attribute = self._scalars[named.name]
            self._models[name] = Model(
                name,
                description=named.description or "",
                alias_of=TypeRef(attribute),
                imports={attribute: module},
            )
        return TypeRef.model(name)

    def _input_object(self, named: Any) -> TypeRef:
        from graphql import Undefined, is_non_null_type

        name = self._name(named.name)
        if name in self._models:
            return TypeRef.model(name)
        model = Model(name, description=named.description or "")
        self._models[name] = model  # before its fields: input types may refer to themselves
        taken: set[str] = set()
        for wire_name, field in named.fields.items():
            python_name = unique(snake_case(wire_name), taken, MODEL_RESERVED)
            required = is_non_null_type(field.type) and field.default_value is Undefined
            model.fields.append(
                ModelField(
                    name=python_name,
                    alias=wire_name if python_name != wire_name else None,
                    type=self.input(field.type),
                    required=required,
                    description=field.description or "",
                )
            )
        return TypeRef.model(name)

    def _name(self, schema_name: str) -> str:
        if schema_name not in self._names:
            self._names[schema_name] = unique(pascal_case(schema_name), self._taken, frozenset())
        return self._names[schema_name]


def wrap(graphql_type: Any, leaf: Any) -> TypeRef:
    """graphql_type's lists and nullability around leaf(named type): [Int!] -> list[int] | None."""
    from graphql import is_list_type, is_non_null_type

    nullable = not is_non_null_type(graphql_type)
    inner = graphql_type if nullable else graphql_type.of_type
    if is_list_type(inner):
        item = wrap(inner.of_type, leaf)
        ref = TypeRef.of(f"list[{item.expr}]", item)
    else:
        ref = leaf(inner)
    return ref.optional() if nullable else ref
