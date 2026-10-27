from typing import Any

from apiroute.codegen.graphql.collected_definition import CollectedDefinition
from apiroute.codegen.graphql.field_collector import FieldCollector
from apiroute.codegen.graphql.graphql_problem import GraphQLProblem

CURSOR = "after"


class PaginationCheck:
    """What an operation with @paginate must have for the generated method to page: a $after
    variable, and on the connection, pageInfo { hasNextPage endCursor } plus nodes or
    edges { node }, unaliased, since the paginator reads those keys."""

    def __init__(self, schema: Any, collector: FieldCollector):
        self._schema = schema
        self._collector = collector

    def problems(self, operation: CollectedDefinition) -> list[GraphQLProblem]:
        mark = operation.paginate
        found = []
        variables = {v.variable.name.value for v in operation.node.variable_definitions or ()}
        if CURSOR not in variables:
            found.append(
                GraphQLProblem.at(
                    mark.field, f"@paginate needs the operation to declare ${CURSOR}: String"
                )
            )
        connection = self._type_at(operation.node, mark.steps)
        if connection is None:
            return found  # an unknown field: validation reports it
        key = mark.path.rsplit(".", 1)[-1]
        if not self._selects_page_info(mark.field, connection):
            found.append(
                GraphQLProblem.at(
                    mark.field,
                    f"@paginate needs {key} to select pageInfo {{ hasNextPage endCursor }}",
                )
            )
        if not self._selects_items(mark.field, connection):
            found.append(
                GraphQLProblem.at(
                    mark.field, f"@paginate needs {key} to select nodes or edges {{ node }}"
                )
            )
        return found

    def _type_at(self, node: Any, steps: tuple) -> Any:
        from graphql import get_named_type

        current = self._schema.get_root_type(node.operation)
        for kind, value in steps:
            if kind == "on":
                current = self._schema.get_type(value) if value else current
                continue
            field = getattr(current, "fields", {}).get(value.name.value)
            if field is None:
                return None
            current = get_named_type(field.type)
        return current

    def _selects_page_info(self, field: Any, connection: Any) -> bool:
        page_info = self._entry(field, connection, "pageInfo")
        if page_info is None:
            return False
        inner = self._entries(page_info.selection_sets, self._field_type(connection, "pageInfo"))
        return all(self._plain(inner.get(name), name) for name in ("hasNextPage", "endCursor"))

    def _selects_items(self, field: Any, connection: Any) -> bool:
        if self._entry(field, connection, "nodes") is not None:
            return True
        edges = self._entry(field, connection, "edges")
        if edges is None:
            return False
        inner = self._entries(edges.selection_sets, self._field_type(connection, "edges"))
        return self._plain(inner.get("node"), "node")

    def _entry(self, field: Any, connection: Any, name: str) -> Any:
        if field.selection_set is None:
            return None
        entry = self._entries([field.selection_set], connection).get(name)
        return entry if self._plain(entry, name) else None

    def _entries(self, selection_sets: list, graphql_type: Any) -> dict:
        from graphql import is_object_type

        if graphql_type is None:
            return {}
        if is_object_type(graphql_type):
            applies = self._collector.for_object(graphql_type)
        else:
            applies = self._collector.for_abstract(graphql_type)
        return self._collector.collect(selection_sets, applies)

    @staticmethod
    def _field_type(parent: Any, name: str) -> Any:
        from graphql import get_named_type

        field = getattr(parent, "fields", {}).get(name)
        return get_named_type(field.type) if field is not None else None

    @staticmethod
    def _plain(entry: Any, name: str) -> bool:
        """Selected under its own name, not aliased to another (or another field as it)."""
        return entry is not None and entry.field_name == name
