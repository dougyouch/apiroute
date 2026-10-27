## 1. Runtime

- [x] 1.1 `GraphQLBody` persisted modes ("hash", "register") with the SHA-256 computed once
- [x] 1.2 `graphql_route(persisted=)` and `GraphQLRouteOptions.persisted`; the builder makes the hash and register specs
- [x] 1.3 `GraphQLPersistedCall` (sync and async): hash first, register on a miss, full documents when unsupported (per route and client instance, weakly held), and recognition by code or message
- [x] 1.4 `GraphQLRouteMethod`: compile the variants, bind through the persisted call, and compose with pagination's `page_call`
- [x] 1.5 Tests: `GraphQLBody` modes and hash, and every scenario in the spec through `MockTransport` (cached, miss, next call, error after registering, unsupported and per-instance memory, other errors, async, paginated)

## 2. Codegen

- [x] 2.1 `--persisted-queries` flag, `GraphQLOperationSpec.persisted`, and `DictClientEmitter` writing `persisted=True`
- [x] 2.2 Tests: the flag, a generated call hashing the document in the file, and output unchanged without it

## 3. Docs and checks

- [x] 3.1 README: persisted queries in the GraphQL section and `--persisted-queries` in "GraphQL clients"; the client-repository skill
- [x] 3.2 Ruff, the full suite, the lowest-dependencies run, and a check against a real APQ server (Apollo Server, run locally): a miss and registration, a cached hit, pagination, and a server with APQ turned off
