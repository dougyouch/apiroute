import re
from typing import Any

from apiroute.codegen.api_definition import Model, Operation, RestPagination
from apiroute.codegen.openapi.ref_resolver import RefResolver
from apiroute.codegen.openapi.schema_mapper import SchemaMapper
from apiroute.codegen.pagination.operation_facts import OperationFacts
from apiroute.codegen.pagination.pagination_rules import PaginationRules
from apiroute.codegen.pagination.speakeasy_pagination import speakeasy_strategy
from apiroute.codegen.pagination.strategy_call import StrategyCall
from apiroute.codegen.type_ref import TypeRef

EXTENSION = "x-speakeasy-pagination"
_LIST = re.compile(r"^list\[(.*)\]$")


class OpenApiPagination:
    """Decides whether an operation pages, by the first --pagination rule matching it, else by
    its x-speakeasy-pagination extension, and finds the type of its items: the item schema of
    the array at the strategy's items path in the success response."""

    def __init__(
        self,
        resolver: RefResolver,
        mapper: SchemaMapper,
        models: dict[str, Model],
        rules: PaginationRules | None,
        warnings: list[str],
    ):
        self._resolver = resolver
        self._mapper = mapper
        self._models = models
        self._rules = rules
        self._warnings = warnings

    def read(self, operation: Operation, raw: dict, schema: Any) -> RestPagination | None:
        schema = self._resolver.deref(schema)
        rule = None if self._rules is None else self._rules.match(self._facts(operation, schema))
        if rule is not None:
            try:
                return self._pagination(operation, rule.strategy, schema)
            except ValueError as error:
                raise ValueError(f"{operation.operation_id}: {rule.label}: {error}") from error
        if EXTENSION not in raw:
            return None
        try:
            return self._pagination(operation, speakeasy_strategy(raw[EXTENSION]), schema)
        except ValueError as error:
            self._warnings.append(f"{operation.operation_id}: {EXTENSION}: {error}; not paginated")
            return None

    def _facts(self, operation: Operation, schema: Any) -> OperationFacts:
        return OperationFacts(
            operation_id=operation.operation_id,
            method=operation.method,
            parameters=frozenset(parameter.wire_name for parameter in operation.parameters),
            is_array=isinstance(schema, dict) and schema.get("type") == "array",
            properties=frozenset(self._properties(schema)),
        )

    def _pagination(self, operation: Operation, call: StrategyCall, schema: Any) -> RestPagination:
        item_schema = self._item_schema(schema, call.items)
        if item_schema is None:
            where = f"items {call.items!r}" if call.items else "the response"
            raise ValueError(f"{where} isn't an array in the success response")
        return RestPagination(
            strategy=call.class_name,
            arguments=call.arguments,
            item=self._item_type(operation.response, call.items),
            item_plain=self._mapper.plain(item_schema),
        )

    def _item_schema(self, schema: Any, path: str) -> Any:
        """The item schema of the array at path; None when there's no array there."""
        for key in filter(None, path.split(".")):
            schema = self._properties(schema).get(key)
        schema = self._resolver.deref(schema)
        if not isinstance(schema, dict) or schema.get("type") != "array":
            return None
        return schema.get("items", {})

    def _properties(self, schema: Any) -> dict[str, Any]:
        """An object schema's properties, its allOf parts' included, each dereferenced."""
        schema = self._resolver.deref(schema)
        if not isinstance(schema, dict):
            return {}
        properties = {}
        for part in schema.get("allOf", []):
            properties.update(self._properties(part))
        for name, value in schema.get("properties", {}).items():
            properties[name] = self._resolver.deref(value)
        return properties

    def _item_type(self, response: TypeRef | None, path: str) -> TypeRef | None:
        """The item model type, read from the response type already mapped (so an inline item
        object isn't mapped a second time, under another name); None when it's Any."""
        current = response
        for key in filter(None, path.split(".")):
            model = self._model(current)
            field = (
                None
                if model is None
                else next((f for f in model.fields if (f.alias or f.name) == key), None)
            )
            current = None if field is None else field.type
        current = self._unaliased(current)
        match = None if current is None else _LIST.match(current.expr.removesuffix(" | None"))
        if match is None or match.group(1) == "Any":
            return None
        return TypeRef(match.group(1), current.models)

    def _model(self, ref: TypeRef | None) -> Model | None:
        ref = self._unaliased(ref)
        if ref is None:
            return None
        return self._models.get(ref.expr.removesuffix(" | None"))

    def _unaliased(self, ref: TypeRef | None) -> TypeRef | None:
        """ref, or what the alias model it names stands for."""
        while ref is not None:
            model = self._models.get(ref.expr.removesuffix(" | None"))
            if model is None or model.alias_of is None:
                return ref
            ref = model.alias_of
        return ref
