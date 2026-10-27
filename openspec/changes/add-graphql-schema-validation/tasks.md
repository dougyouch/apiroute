## 1. Section hook

- [x] 1.1 Add a no-op `RouteMethod.nested_in(root)` hook
- [x] 1.2 Have `Router.__init_subclass__` call it, after installing sections, for the routes of each nested section class, recursively
- [x] 1.3 Tests: a recording `RouteMethod` subclass sees `nested_in` for the enclosing section and then the client, in that order

## 2. Schema loading

- [x] 2.1 `GraphQLSchemaLoader`: accepts a `GraphQLSchema`, or a path resolved against the declaring class's module; reads `.json` introspection (with or without the `data` envelope) or SDL; caches by absolute path; raises `ValueError` with the path for missing or invalid files and a clear message when graphql-core is missing
- [x] 2.2 Tests in `tests/graphql/test_graphql_schema_loader.py`: SDL, introspection in both shapes, a schema object, relative resolution, a missing file, invalid SDL, bad JSON, caching, and graphql-core missing

## 3. Validation

- [x] 3.1 `check_against_schema(document, schema)`: parse, validate, and raise one `ValueError` listing every problem with its line and column
- [x] 3.2 Add `validate` to `graphql_route` and `GraphQLRouteOptions`
- [x] 3.3 `GraphQLRouteMethod`: record enclosing classes from `nested_in`; find the schema (own class first, then enclosing classes); validate in `_spec_for` and in `nested_in` for eagerly compiled routes, once; wrap errors as `RouteDefinitionError`
- [x] 3.4 Tests in `tests/graphql/test_graphql_schema_check.py` and `tests/graphql/test_graphql_schema_validation.py` covering every scenario in the spec: unknown field, wrong variable type, several errors, valid routes, lazy classes, subclass inheritance, sections (one and two levels deep), a section opting out, `validate=False`, missing file, graphql-core missing, and a shared schema loaded once

## 4. Docs and release

- [x] 4.1 README GraphQL section: `graphql_schema`, path resolution, sections, `validate=False`, and the load cost of large schemas; replace "Documents aren't checked against a schema"
- [x] 4.2 Run `uv run ruff check .`, `uv run ruff format --check .` and `uv run pytest`
