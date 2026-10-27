## 1. Setup and shared loading

- [ ] 1.1 Add `graphql-core>=3.2` to the `codegen` extra, and `uv lock`
- [ ] 1.2 Expose `load_schema_file(path)` from `apiroute/graphql/graphql_schema_loader.py` (with the existing cache and introspection tolerance), and have `load_schema(holder)` use it
- [ ] 1.3 Test fixtures in `tests/codegen/fixtures/graphql/`: a schema (objects, an interface, a union, an enum, an input, a custom scalar, a deprecated field) and an `ops/` tree with root files, a `repos/` section, shared fragments and a mutation

## 2. Reading operations

- [ ] 2.1 `GraphQLOperationCollector`: read `*.graphql`/`*.gql` under the directory in path order; record each definition's file and section; collect problems for anonymous operations, subscriptions and duplicate names
- [ ] 2.2 Per-operation documents: the operation plus its transitive fragments; `__typename` added where type conditions need it; `print_ast` output; leading-comment docstrings
- [ ] 2.3 Validation of each document with `graphql.validate`, with locations mapped back to file:line:column; deprecation and unused-fragment warnings; all problems raised together
- [ ] 2.4 Tests: each validation and warning scenario in the spec, location mapping across files, and `__typename` insertion

## 3. Mapping to the ApiDefinition

- [ ] 3.1 `ApiDefinition` additions: `GraphQLOperationSpec` and `Operation.graphql`, and the `"variable"` parameter location
- [ ] 3.2 `GraphQLTypeMapper`: scalars (built-in and `--scalar`), enums as Literal aliases, and input objects as models (reachable ones only)
- [ ] 3.3 `SelectionModelMapper`: result models from selection sets, covering naming, aliases, nullability, conditional fields, flattened fragments, field merging, and interfaces/unions with `__typename` Literals and a fallback model
- [ ] 3.4 `GraphQLReader`: schema source (file or introspection URL with headers), operations, sections, `--endpoint` split, producing the `ApiDefinition`
- [ ] 3.5 Tests in `tests/codegen/graphql/` for the mappers and reader: each model-shape scenario in the spec

## 4. Emitting

- [ ] 4.1 `DictClientEmitter`: a GraphQL route branch (`graphql_route` with the inlined document, `path=`, `variables=` only when needed, keyword-only variables, imports)
- [ ] 4.2 `ModelsClientEmitter`: variable parameters in typed signatures
- [ ] 4.3 `PackageEmitter`: a source line naming the schema and operations
- [ ] 4.4 Tests: generate the fixture package, import it, call dict and typed methods (sync and `.aio`) against `MockTransport` with `graphql_response`, check sent documents and variables, parse union results, and run `ruff check`/`ruff format --check` on the output; generating twice gives identical files; OpenAPI/WSDL package tests are unchanged

## 5. CLI

- [ ] 5.1 `generate graphql`: `--operations` (required), `--endpoint`, `--header`, `--scalar`, and the shared options; refuse `--base-url`; the summary line counts operations and models; errors and warnings printed as for other formats
- [ ] 5.2 `fetch-schema`: introspection POST with headers, SDL or JSON output, and failures reported without writing
- [ ] 5.3 Tests in `tests/codegen/test_cli.py`: success, validation failure leaves the output untouched, the introspection URL with headers (through a mock transport), fetch-schema SDL/JSON, a 401, and graphql-core missing

## 6. Docs and skill

- [ ] 6.1 README "Code generation": the GraphQL workflow (fetch-schema, operations layout, generate, the typed layer, `--scalar`), with an example
- [ ] 6.2 `.agent/skills/apiroute-client.md`: `format: graphql` entries (schema URL, `operations` directory, introspection headers from the environment), `fetch-schema` in `scripts/generate.py`, operations as hand-written inputs in the repository layout
- [ ] 6.3 AGENT.md layout: `codegen/graphql/`
- [ ] 6.4 Run `uv run ruff check .`, `uv run ruff format --check .`, `uv run python -m pytest`, and the lowest-dependencies run (`uv run --isolated --resolution lowest-direct --python 3.10 --group dev python -m pytest`)
