## Why

Most real GraphQL lists are Relay connections: `issues(first: $first, after: $after) { pageInfo { hasNextPage endCursor } nodes { ... } }`. To read them all today, every caller writes the same loop: call, collect `nodes`, check `hasNextPage`, feed `endCursor` back as `$after`, repeat. Testing against GitHub's API for 1.9.0 needed exactly that loop to page through cpython's issues. It's easy to get subtly wrong (forgetting `hasNextPage`, or looping forever on a server that repeats a cursor), and typed clients lose their types in it. GitHub, Shopify, Linear and most other GraphQL APIs page this way, so this is the most common thing a GraphQL client does after a single call.

## What Changes

- **`graphql_route(..., paginate="repository.issues")`:** the method returns an iterator over the connection's items, across every page. It requests the next page lazily as iteration reaches it, passing the last `endCursor` as the `$after` variable (`cursor=` names another variable). Items are the connection's `nodes`, or each `edges[].node`, converted by `model=` or by the item type of an `Iterator[...]` return annotation. Through `.aio`, it returns an async iterator.
- **Checks:**
  - When the class is created: the operation must declare the cursor variable, and `data=` can't be combined with `paginate=`.
  - While iterating: a page whose connection lacks `pageInfo { hasNextPage endCursor }`, or `nodes`/`edges { node }`, raises a clear error. So does a server that answers `hasNextPage` with no cursor or with the same cursor again, instead of looping forever.
  - A null connection (e.g. a repository that doesn't exist) yields nothing.
- **Codegen:** a client-side `@paginate` directive on a connection field in a `.graphql` operation file makes the generated method paginate there.
  - The directive is removed from the document that's sent, and the generator checks the connection's shape and the `$after` variable, reporting problems as `file:line:column`.
  - The dict method returns `Iterator[dict[str, Any]]`. With `--models`, the typed method returns `Iterator[<item model>]`, validating items one at a time.
- **`TypedClient`** gains `_paginate()`, the typed counterpart of `_call()`, for iterators of items (sync or async).

Not in scope: backward paging (`last`/`before`), access to page-level data (total counts) during iteration, and a page-size option (the operation's own `$first` controls it).

## Capabilities

### New Capabilities
- `graphql-pagination`: iterating Relay connections across pages, at run time (`graphql_route(paginate=)`) and in generated clients (`@paginate`).

### Modified Capabilities
<!-- None: graphql-routes and graphql-codegen requirements are unchanged; pagination is additive. -->

## Impact

- **Runtime:**
  - new `apiroute/graphql/graphql_paginator.py`;
  - `graphql_route`, `GraphQLRouteOptions`, `GraphQLRouteBuilder` and `GraphQLRouteMethod` (which wraps its bound method when paginating);
  - `TypedClient._paginate`.
- **Codegen:**
  - the operation collector (reads and strips `@paginate`);
  - a connection check;
  - `GraphQLOperationSpec.paginate`;
  - the dict and models client emitters (return types and `paginate=`).
- **Generated output:** only operations that use `@paginate` change. Everything else is byte-identical.
- **Release:** `feat:` (minor). No new dependencies.
