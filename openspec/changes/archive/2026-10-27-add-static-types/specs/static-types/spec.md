## ADDED Requirements

### Requirement: Decorated routes keep their signatures for type checkers
A route declared with `@route(...)` or `@graphql_route(...)` on a `def` SHALL be typed, through a client or section instance, as the decorated method's signature without `self` and with its return annotation, in both mypy and pyright. Calls with wrong argument types or unknown arguments SHALL be type errors.

#### Scenario: Signature and return type
- **WHEN** a client declares `@route("/users/{name}") def get_user(self, name: str, *, full: bool = False) -> dict[str, int]: ...`
- **THEN** a type checker sees `client.get_user` as `(name: str, *, full: bool = False) -> dict[str, int]`, and `client.get_user("x")` as `dict[str, int]`

#### Scenario: Wrong arguments
- **WHEN** code calls `client.get_user(123)` or `client.get_user("x", nope=1)`
- **THEN** mypy and pyright report an error

#### Scenario: A paginated GraphQL route
- **WHEN** a `paginate=` route is annotated `-> Iterator[Issue]`
- **THEN** iterating its result gives `Issue` to a type checker

### Requirement: Client and response sentinels type-check
`FROM_CLIENT` SHALL be a valid default for a parameter of any type. A keyword-only route parameter whose default is `FROM_RESPONSE` SHALL receive the processed response, as a `Result`-annotated one does (converted to its annotation's model type when that's a model), SHALL be left out of the call signature, and SHALL NOT be required of callers by type checkers.

#### Scenario: FROM_CLIENT default
- **WHEN** a route declares `def list_repos(self, org: str = FROM_CLIENT) -> list[dict[str, Any]]: ...`
- **THEN** mypy reports no error, and `client.list_repos()` is `list[dict[str, Any]]`

#### Scenario: FROM_RESPONSE hook
- **WHEN** a route declares `def get_login(self, name: str, *, data: dict[str, str] = FROM_RESPONSE) -> str: return data["login"]`
- **THEN** `client.get_login("x")` returns the response's login, its signature is `(name)`, and a type checker sees it as `str` without asking for `data`

### Requirement: Routes without a def are accepted
A route assigned without a `def` (`get_user = route("/users/:name")`, or `graphql_route(...)` assigned) SHALL be typed as a callable accepting any arguments and returning `Any`, with no type errors at call sites.

#### Scenario: Generated signature
- **WHEN** code calls `client.get_user(name="x")` on a route declared without a `def`
- **THEN** mypy and pyright report no error, and the result is `Any`

### Requirement: Nested sections don't produce false errors
A `Section` class nested in a client SHALL be typed as an instance of that section when reached through a client instance, in pyright. In mypy, routes reached through it SHALL type-check as `Any` without errors. Run-time behavior SHALL be unchanged.

#### Scenario: pyright
- **WHEN** a client nests `class issues(Section)` with `@route(...) def list(self, state: str | None = None) -> list[str]: ...`
- **THEN** pyright sees `client.issues.list()` as `list[str]`, and flags `client.issues.list(state=5)`

#### Scenario: mypy
- **WHEN** the same code is checked with mypy
- **THEN** it reports no error for `client.issues.list()`

### Requirement: Generated clients are typed end to end
Generated clients SHALL annotate their section and `.models` attributes with their classes (imported only for type checkers), and SHALL NOT import them at run time until used. Generated dict `client.py` files SHALL silence mypy's `empty-body` check for their route stubs. Typed calls SHALL be typed as their response models, and `TypedClient.with_options()` SHALL return the same view type. Generated packages SHALL type-check with mypy with no errors.

#### Scenario: Typed call through a section
- **WHEN** a generated package is used as `client.pets.models.get_pet(1)`
- **THEN** a type checker sees the generated response model type, and its fields

#### Scenario: Lazy loading unchanged
- **WHEN** only the root client of a generated package is imported and constructed
- **THEN** no section or models module has been imported

#### Scenario: Generated package type-checks
- **WHEN** mypy or pyright checks a generated OpenAPI, WSDL or GraphQL package
- **THEN** it reports no errors

#### Scenario: Route bodies
- **WHEN** a generated route has a docstring
- **THEN** its body ends with `...` after the docstring
