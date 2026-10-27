## ADDED Requirements

### Requirement: Persisted routes send a hash first
`graphql_route(..., persisted=True)` SHALL send each call without `query`, with `extensions.persistedQuery` set to `{"version": 1, "sha256Hash": <lowercase hex SHA-256 of the route's exact document in UTF-8>}`, alongside `operationName` and `variables` as usual. When the server answers with data, that call SHALL return it like any route.

#### Scenario: A cached query
- **WHEN** a persisted route is called and the server answers `{"data": {...}}`
- **THEN** exactly one request was sent, its body has no `query` and has the extension with the document's SHA-256, and the call returns the data

### Requirement: A miss registers the document
When the hash-only request is answered with a GraphQL error recognized as `PersistedQueryNotFound` (message `PersistedQueryNotFound` or `extensions.code` `PERSISTED_QUERY_NOT_FOUND`, on HTTP 200 or 400), the route SHALL send one more request with both `query` and the extension, and return that response's result. Later calls SHALL start with the hash-only request again.

#### Scenario: First call to a fresh server
- **WHEN** the first request is answered `{"errors": [{"message": "PersistedQueryNotFound", "extensions": {"code": "PERSISTED_QUERY_NOT_FOUND"}}]}` and the second with data
- **THEN** the call returns the data, the second request carried `query` and the extension, and no `GraphQLError` reached the caller

#### Scenario: The next call
- **WHEN** the same route is called again
- **THEN** its first request is hash-only

#### Scenario: A real error after registering
- **WHEN** the register request is answered with a different GraphQL error
- **THEN** the call raises that `GraphQLError`

### Requirement: Servers without APQ get full documents
When the hash-only request is answered with an error recognized as `PersistedQueryNotSupported` (message `PersistedQueryNotSupported` or code `PERSISTED_QUERY_NOT_SUPPORTED`), the route SHALL send the full document without the extension, return that result, and send full documents without the extension for later calls of that route on that client instance. Other client instances SHALL NOT be affected.

#### Scenario: Unsupported server
- **WHEN** the first request is answered `PersistedQueryNotSupported` and the second with data
- **THEN** the call returns the data, and the next call sends one request with `query` and no extension

#### Scenario: Another client
- **WHEN** a second client instance calls the same route
- **THEN** its first request is hash-only

### Requirement: Other errors propagate
A hash-only request answered with any other GraphQL error SHALL raise that `GraphQLError` without another request. Non-GraphQL failures (HTTP errors, network errors after retries) SHALL propagate as for any route.

#### Scenario: Validation error
- **WHEN** the hash-only request is answered `{"errors": [{"message": "Cannot query field"}]}`
- **THEN** the call raises `GraphQLError` after one request

### Requirement: Persisted queries work with async calls and pagination
Calls through `.aio` SHALL follow the same protocol. A route with both `persisted=True` and `paginate=` SHALL send every page hash-first, registering on a miss as above.

#### Scenario: Async miss
- **WHEN** a persisted route is awaited through `.aio` and the server misses the hash
- **THEN** the awaited result is the data from the register request

#### Scenario: Paginated and persisted
- **WHEN** a persisted, paginated route is iterated over two pages on a server that has the hash
- **THEN** both page requests are hash-only, and the second carries the cursor variable

### Requirement: Generated clients can use persisted queries
`apiroute generate graphql --persisted-queries` SHALL generate every route with `persisted=True`. Without the flag, the generated files SHALL be unchanged.

#### Scenario: Flag given
- **WHEN** a package is generated with `--persisted-queries`
- **THEN** each `graphql_route` in it has `persisted=True`, and calling it sends the hash of the document shown in the file

#### Scenario: Flag absent
- **WHEN** the same package is generated without the flag
- **THEN** its files are identical to those generated before this change
