# graphql-codegen Specification

## Purpose
TBD - created by archiving change add-graphql-codegen. Update Purpose after archive.
## Requirements
### Requirement: Generate a client from a schema and operation files
`apiroute generate graphql <schema> --operations <dir> -o <out>` SHALL write a client package with one method per named operation found in the `.graphql` and `.gql` files under `<dir>`. `<schema>` SHALL be accepted as an SDL file, a `.json` introspection result, or an `http(s)` endpoint introspected with any `--header "Name: value"` given.

#### Scenario: Root operations
- **WHEN** `ops/viewer.graphql` holds `query Viewer { viewer { login } }`
- **THEN** the generated root client has a `viewer()` method that sends that operation

#### Scenario: Introspecting an endpoint
- **WHEN** `<schema>` is `https://api.example.test/graphql` and `--header "Authorization: Bearer t"` is given
- **THEN** the schema is fetched by an introspection POST that carries that header

#### Scenario: graphql-core missing
- **WHEN** the codegen extra's graphql-core isn't installed
- **THEN** the command exits non-zero with a message naming `apiroute[codegen]`

### Requirement: Subdirectories become sections
Operation files directly in `<dir>` SHALL become root-client methods. Files under a first-level subdirectory, at any depth, SHALL become methods of a `Section` named after that subdirectory. Fragments SHALL be shared across all files.

#### Scenario: A section per folder
- **WHEN** `ops/repos/stars.graphql` holds `query Stars(...) { ... }`
- **THEN** the client has `client.repos.stars(...)`, defined on a generated `ReposSection`

#### Scenario: A fragment from another file
- **WHEN** `ops/fragments.graphql` defines `fragment RepoFields on Repository { name }` and `ops/repos/repo.graphql` spreads `...RepoFields`
- **THEN** the generated `repo` method's document includes `fragment RepoFields`

### Requirement: Operations are validated before anything is written
The generator SHALL validate every operation (with the fragments it uses) against the schema, and check that operations are named, that operation and fragment names are unique, and that no operation is a subscription. Any problem SHALL fail the command with a non-zero exit, listing every problem across all files with its file, line and column, and SHALL leave the output directory unchanged. Uses of deprecated fields or enum values SHALL be printed as warnings with the deprecation reason and SHALL NOT fail the command. Unused fragments SHALL be warnings.

#### Scenario: Errors in two files
- **WHEN** `a.graphql` queries an unknown field and `b.graphql` passes a variable of the wrong type
- **THEN** the command exits 1, prints both problems with `a.graphql:<line>:<column>` and `b.graphql:<line>:<column>`, and writes no files

#### Scenario: Anonymous operation
- **WHEN** a file holds `query { viewer { login } }`
- **THEN** the command fails, saying operations must be named, with the file and line

#### Scenario: Duplicate names
- **WHEN** two files both define `query Viewer`
- **THEN** the command fails, naming both locations

#### Scenario: Deprecated field
- **WHEN** an operation selects a field marked `@deprecated(reason: "Use x")`
- **THEN** the package is generated and a warning names the field, its location and "Use x"

### Requirement: Dict methods send the document and return data
Each generated dict-layer method SHALL be a `graphql_route` whose document is the operation followed by the fragments it uses (transitively), printed by graphql-core in a normalized form. It SHALL take one keyword-only parameter per variable (snake_case, required first, optional ones defaulting to `None`) and return the operation's `data` as a dict. The leading `#` comment of an operation SHALL become its docstring. Where a selection on an interface or union has type conditions, `__typename` SHALL be added to it in the emitted document when missing.

#### Scenario: Variables and docstring
- **WHEN** `ops/repo.graphql` holds `# A repository.\nquery Repo($owner: String!, $repoName: String!, $first: Int) { ... }`
- **THEN** the method is `def repo(self, *, owner: str, repo_name: str, first: int | None = None) -> dict[str, Any]` with docstring "A repository.", and calling it sends `{"owner", "repoName", "first"}` variables

#### Scenario: A variable that isn't a valid Python name
- **WHEN** an operation declares `$from: String`
- **THEN** the parameter is `from_` and the route maps `variables={"from": "from_"}`

#### Scenario: Typename for unions
- **WHEN** an operation selects `search { ... on User { login } ... on Repository { name } }` without `__typename`
- **THEN** the emitted document selects `__typename` in that selection set

### Requirement: Typed methods return models shaped by the selection
With `--models`, the generator SHALL emit pydantic result models shaped by each operation's selection set, and a `.models` view whose methods take input models and return the result model. The root model SHALL be `<Operation>Result`, with nested models named `<Parent><Field>`. Field names SHALL be snake_case with wire aliases. Aliased GraphQL fields SHALL use the alias. A non-null field SHALL be required. A nullable field SHALL be `T | None`. A field that may be absent (`@include`/`@skip`, or in a type-conditioned fragment) SHALL default to `None`. Fragment fields SHALL be merged into the selecting model.

#### Scenario: Nested result
- **WHEN** `query Repo { repository(owner: "a", name: "b") { name owner { login } } }` is generated with `--models`
- **THEN** `client.models.repo()` returns a `RepoResult` whose `.repository` is a `RepoRepository | None` with `.name: str` and `.owner: RepoRepositoryOwner`

#### Scenario: Alias
- **WHEN** a selection is `author: owner { login }`
- **THEN** the model has a field `author` typed by a model named `...Author`

#### Scenario: Conditional field
- **WHEN** a field is selected with `@include(if: $full)`
- **THEN** its model field defaults to `None`

#### Scenario: Union with type conditions
- **WHEN** an operation selects `search { ... on User { login } ... on Repository { name } }`
- **THEN** the field's type is a union of `...User` and `...Repository` models, each with a `typename` Literal field aliased `__typename`, plus a fallback model for other possible types, and a response is parsed into the model matching its `__typename`

### Requirement: Inputs, enums and scalars are typed
With `--models`, the generator SHALL emit pydantic models for input object types and `Literal` aliases for enums reachable from some operation's variables or results, and no others. Built-in scalars SHALL map to `int`, `float`, `str` and `bool`. Custom scalars SHALL map to `Any`, unless `--scalar Name=module:attr` maps one to an importable type.

#### Scenario: Input object variable
- **WHEN** `mutation Star($input: AddStarInput!)` is generated with `--models`
- **THEN** `client.models.star(input=AddStarInput(starrable_id="x"))` sends `{"input": {"starrableId": "x"}}`

#### Scenario: Custom scalar mapping
- **WHEN** `--scalar DateTime=datetime:datetime` is given and a selected field is `DateTime!`
- **THEN** the model field is typed `datetime` and a response's ISO string is parsed into a `datetime`

#### Scenario: Unmapped custom scalar
- **WHEN** a selected field's type is the custom scalar `URI` and no `--scalar` maps it
- **THEN** the field is typed `Any`

### Requirement: Endpoint and shared generator options
`--endpoint URL` SHALL set the root client's `base_url` to the URL without its path, and each route's `path` to the URL's path. Without it, routes SHALL use `/graphql` and no `base_url` SHALL be generated. `--client-name`, `--base-class`, `--models` and `--no-format` SHALL behave as for the other formats. Regeneration SHALL follow the same marker rules.

#### Scenario: Endpoint split
- **WHEN** `--endpoint https://api.github.com/graphql` is given
- **THEN** the root client has `base_url = "https://api.github.com"` and routes use `path="/graphql"`

#### Scenario: Base class
- **WHEN** `--base-class myapi.auth:GitHubAuth` is given
- **THEN** the root client extends `GitHubAuth`

### Requirement: Output is deterministic and lint-clean
Generating twice from the same inputs SHALL produce byte-identical files. The generated package SHALL pass `ruff check` and `ruff format --check` with the repository's settings, and SHALL import on Python 3.10.

#### Scenario: Regenerate
- **WHEN** the same schema and operations are generated into two directories
- **THEN** every file is identical

### Requirement: Fetch a schema by introspection
`apiroute fetch-schema <endpoint> -o <file> [--header "Name: value"]...` SHALL introspect the endpoint and write the schema as SDL, or as the introspection JSON when `<file>` ends in `.json`. A failed request or an introspection response with errors SHALL exit non-zero with the reason.

#### Scenario: SDL snapshot
- **WHEN** `apiroute fetch-schema https://api.example.test/graphql -o schema.graphql` succeeds
- **THEN** `schema.graphql` holds the printed SDL, which `generate graphql` accepts

#### Scenario: Unauthorized
- **WHEN** the endpoint answers 401
- **THEN** the command exits 1 with the status in its message, and writes no file

