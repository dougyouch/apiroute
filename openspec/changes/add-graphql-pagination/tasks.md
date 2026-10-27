## 1. Runtime paging

- [x] 1.1 `GraphQLPaginator`: argument binding, connection lookup along the path, items from `nodes` or `edges[].node`, `pageInfo` checks, the forever-loop guard, and sync and async wrapping
- [x] 1.2 `graphql_route(paginate=, cursor=)`: options; builder checks (cursor variable declared, no `data=`); the page request isn't converted; item converter from `model=` or an iterator annotation
- [x] 1.3 `GraphQLRouteMethod.bind` wraps paginated routes
- [x] 1.4 Tests in `tests/graphql/test_graphql_paginator.py` and `tests/graphql/test_graphql_pagination.py`: every runtime scenario in the spec (pages, laziness, edges, starting cursor, null connection, later-page errors, checks, conversion, async)

## 2. Typed client

- [x] 2.1 `TypedClient._paginate` (sync and async, lazy validation)
- [x] 2.2 Tests in `tests/test_typed_client.py`

## 3. Codegen

- [x] 3.1 Collector: find and strip `@paginate` in operations, record the response-key path, report duplicates and uses in fragments
- [x] 3.2 Connection check (`$after` declared; unaliased `pageInfo { hasNextPage endCursor }`; `nodes` or `edges { node }`) with locations
- [x] 3.3 Reader: `GraphQLOperationSpec.paginate`, item model found along the path, and a paginated flag on the operation
- [x] 3.4 Emitters: `paginate=` and `Iterator[...]` return types in dict and typed methods, `_paginate` calls, and `collections.abc` imports
- [x] 3.5 Tests: collector and checks, reader, a generated package paging through `MockTransport` (dict, typed, `.aio`), and output unchanged without `@paginate` (fixture package compared before and after)

## 4. Docs and checks

- [x] 4.1 README: pagination in the GraphQL section and in "GraphQL clients" (`@paginate`)
- [x] 4.2 Client-repository skill: `@paginate` in operations
- [x] 4.3 Ruff, the full suite, the lowest-dependencies run, and a live check against GitHub (paging cpython's issues, read-only)
