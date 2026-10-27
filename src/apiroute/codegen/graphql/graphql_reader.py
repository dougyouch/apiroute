from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from apiroute.base_url_validator import validate_base_url
from apiroute.codegen.api_definition import (
    ApiDefinition,
    GraphQLOperationSpec,
    Group,
    Model,
    Operation,
    Parameter,
)
from apiroute.codegen.graphql.collected_definition import CollectedDefinition
from apiroute.codegen.graphql.graphql_type_mapper import GraphQLTypeMapper
from apiroute.codegen.graphql.operation_collector import OperationCollector
from apiroute.codegen.graphql.operation_documents import OperationDocuments
from apiroute.codegen.graphql.paginated_item import paginated_item
from apiroute.codegen.graphql.schema_fetcher import SchemaFetcher
from apiroute.codegen.graphql.selection_model_mapper import SelectionModelMapper
from apiroute.codegen.python_names import RESERVED, pascal_case, snake_case, unique

DEFAULT_PATH = "/graphql"


class GraphQLReader:
    """Reads a schema and a directory of operations into an ApiDefinition: one Operation per
    named operation, grouped into the root and one section per first-level subdirectory.

    Every operation is validated first; any problem, in any file, raises ValueError listing
    them all, before anything is generated."""

    def __init__(
        self,
        schema: str,
        operations: str,
        client_name: str,
        endpoint: str | None = None,
        headers: dict[str, str] | None = None,
        scalars: dict[str, tuple[str, str]] | None = None,
        fetcher: SchemaFetcher | None = None,
        persisted: bool = False,
    ):
        self._schema_source = schema
        self._operations_dir = operations
        self._client_name = client_name
        self._endpoint = endpoint
        self._headers = headers or {}
        self._scalars = scalars or {}
        self._fetcher = fetcher or SchemaFetcher()
        self._persisted = persisted

    def read(self) -> ApiDefinition:
        _require_graphql_core()
        schema = self._schema()
        collected = OperationCollector(self._operations_dir).collect()
        documents = OperationDocuments(schema, collected)
        problems = collected.problems + documents.problems()
        if problems:
            listed = "\n".join(f"  {problem}" for problem in problems)
            raise ValueError(f"the operations don't match the schema:\n{listed}")
        definition = self._definition(schema)
        definition.warnings = [str(warning) for warning in documents.warnings()]
        self._operations(definition, schema, collected, documents)
        return definition

    def _schema(self) -> Any:
        from apiroute.graphql.graphql_schema_loader import (
            load_schema_file,
            schema_from_introspection,
        )

        if self._schema_source.startswith(("http://", "https://")):
            data = self._fetcher.introspect(self._schema_source, self._headers)
            return schema_from_introspection(data)
        return load_schema_file(self._schema_source)

    def _definition(self, schema: Any) -> ApiDefinition:
        base_url, _ = self._endpoint_parts()
        return ApiDefinition(
            client_name=self._client_name,
            base_url=base_url,
            title=f"{self._client_name}: GraphQL operations",
            description=schema.description or "",
            source=f"{_source_name(self._schema_source)} and {Path(self._operations_dir).name}",
        )

    def _operations(
        self,
        definition: ApiDefinition,
        schema: Any,
        collected: OperationCollector,
        documents: OperationDocuments,
    ) -> None:
        taken: set[str] = set()
        types = GraphQLTypeMapper(definition.models, taken, self._scalars)
        results = SelectionModelMapper(schema, documents.collector, types, definition.models, taken)
        groups = {"": definition.root}
        definition.root.class_name = self._client_name
        group_names: set[str] = set()
        method_names: dict[str, set[str]] = {}
        for collected_operation in collected.operations:
            section = collected_operation.section
            if section not in groups:
                name = unique(snake_case(section), group_names)
                groups[section] = Group(name, f"{pascal_case(section)}Section")
                definition.groups.append(groups[section])
            group = groups[section]
            taken_methods = method_names.setdefault(section, set())
            group.operations.append(
                self._operation(
                    collected_operation, schema, documents, types, results, taken_methods
                )
            )
        definition.models = _ordered(definition.models)

    def _operation(
        self,
        collected: CollectedDefinition,
        schema: Any,
        documents: OperationDocuments,
        types: GraphQLTypeMapper,
        results: SelectionModelMapper,
        taken_methods: set[str],
    ) -> Operation:
        node = collected.node
        operation_name = node.name.value
        prepared, _ = documents.prepared(collected)
        _, path = self._endpoint_parts()
        response = results.result(prepared, operation_name)
        paginate = collected.paginate.path if collected.paginate else None
        if paginate is not None:
            response = paginated_item(types.models, response, paginate)
        return Operation(
            name=unique(snake_case(operation_name), taken_methods, RESERVED),
            method="POST",
            path=path,
            summary=collected.comment,
            parameters=_variables(node, schema, types),
            response=response,
            response_plain="Iterator[dict[str, Any]]" if paginate else "dict[str, Any]",
            operation_id=operation_name,
            graphql=GraphQLOperationSpec(
                document=documents.text(collected),
                operation_name=operation_name,
                operation_type=node.operation.value,
                path=path,
                paginate=paginate,
                persisted=self._persisted,
            ),
        )

    def _endpoint_parts(self) -> tuple[str | None, str]:
        if self._endpoint is None:
            return None, DEFAULT_PATH
        parts = urlsplit(self._endpoint)
        if parts.query or parts.fragment:
            raise ValueError(f"--endpoint takes a URL without a query: {self._endpoint}")
        base_url = f"{parts.scheme}://{parts.netloc}"
        validate_base_url(base_url)
        return base_url, parts.path.rstrip("/")


def _variables(node: Any, schema: Any, types: GraphQLTypeMapper) -> list[Parameter]:
    from graphql import is_non_null_type, type_from_ast

    taken: set[str] = set()
    parameters = []
    for variable in node.variable_definitions or ():
        wire_name = variable.variable.name.value
        graphql_type = type_from_ast(schema, variable.type)
        parameters.append(
            Parameter(
                name=unique(snake_case(wire_name), taken, frozenset({"self"})),
                wire_name=wire_name,
                location="variable",
                type=types.required_input(graphql_type),
                required=is_non_null_type(graphql_type) and variable.default_value is None,
            )
        )
    return parameters


def _source_name(schema: str) -> str:
    """A URL as is, a file by its name, as the other readers name their source."""
    return schema if schema.startswith(("http://", "https://")) else Path(schema).name


def _ordered(models: dict[str, Model]) -> dict[str, Model]:
    """Models by name, so output doesn't depend on the order operations reached them."""
    return {name: models[name] for name in sorted(models)}


def _require_graphql_core() -> None:
    try:
        import graphql  # noqa: F401
    except ImportError as error:
        raise RuntimeError(
            "generating GraphQL clients needs graphql-core: pip install apiroute[codegen]"
        ) from error
