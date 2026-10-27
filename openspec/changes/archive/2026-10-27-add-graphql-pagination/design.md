## Context

A `graphql_route` compiles to a `RouteSpec` through `GraphQLRouteBuilder`, and its `GraphQLRouteMethod` binds to a client like any `RouteMethod`. A bound call runs one request through `RouteExecutor`, with its retries, hooks and decoding, and returns the decoded `data`. `.aio` binds the same method with `is_async=True`, returning a coroutine function.

The generator turns each operation into a `graphql_route`, and with `--models` into a `TypedClient` method that calls `_call(route, response_type, ...)`. `_call` converts input models to plain data and validates the whole result.

## Goals / Non-Goals

**Goals:**
- One option turns a connection-returning operation into "all the items", sync and async, lazily, with every page going through the normal request path: retries, hooks, `GraphQLError`.
- Fail loudly on misconfiguration (at class creation where possible) and on servers that would make the loop run forever.
- Generated clients support the same thing through `@paginate`, with typed items.

**Non-Goals:**
- Backward paging, page-level metadata during iteration, offset or limit pagination, and a built-in page cap (`itertools.islice` stops early).

## Decisions

### 1. Pagination wraps the bound method; each page is an ordinary call

`GraphQLRouteMethod.bind()` binds as today, then, when the route paginates, returns `GraphQLPaginator.wrap(page_call, is_async)`. `page_call(cursor)` gives the bound call for a page: for the first page (cursor `None`) it's the route exactly as called. For later pages it's the route bound with `options.merged(RequestOptions(body={"after": cursor}))`. The body is the variables, and a dict body option merges over the route's, so the cursor variable is set whether or not the method has a parameter for it. The paginator:
1. checks the caller's arguments against the signature up front, so wrong arguments fail on the call rather than on the first `next()`;
2. calls `page_call(cursor)(*args, **kwargs)` for a page and digs the connection out of `data` along the `paginate` path;
3. yields each item, converted if there's an item converter;
4. reads `pageInfo`. It stops when `hasNextPage` is false. When it's true, it takes `endCursor` as the next cursor and goes back to step 2.

Sync, it's a generator. Async, it's an async generator awaiting each page. The first request happens on the first `next()`, as with any generator. `with_options()` applies to every page, because each page is bound with the same options.

*Found testing against GitHub:* the first version set the cursor through the method's `after` parameter. The natural way to write a paginated method leaves that parameter out (`def open_issues(self, owner, name)`), and compiling then failed. Setting the variable through the body option removed the need for the parameter.

*Alternative:* a separate `paginate(client.method, path)` helper. Rejected as the primary API because it splits the operation's description in two (the query here, its shape there), and generated clients couldn't express it. Nothing stops a later helper from reusing `GraphQLPaginator`.

*Alternative:* pagination inside `RouteExecutor`. Rejected because the executor runs one request; paging is a loop over requests and belongs above it.

### 2. Where the cursor goes: a variable, `after` by default

The operation must declare the cursor variable (`$after: String`, or the name given by `cursor=`). This is checked when the class is created, using the variables `GraphQLDocument` already reads. Later pages set that variable directly (Decision 1), so the method needn't declare a parameter for it. A method that does declare one (`after: str | None = None`) lets a caller start mid-list: the first page sends the caller's cursor, and later pages override it.

### 3. What gets yielded

The connection is the value at the dotted `paginate` path inside `data`, following response keys, so an aliased field is named by its alias. Then:
- `nodes` present → each element of it;
- else `edges` present → each edge's `node`;
- neither → `ValueError("... selects neither nodes nor edges { node }")`, raised during iteration with the operation's name.

A null connection, or a null anywhere along the path, yields nothing and stops. A missing repository is "no items", and a `GraphQLError` still raises for real errors.

### 4. Ending, and guarding the loop

- `pageInfo` missing, or missing `hasNextPage`/`endCursor` → `ValueError` naming what the operation must select.
- `hasNextPage` false → stop.
- `hasNextPage` true with a null `endCursor`, or a cursor equal to the previous one → `ValueError("... would page forever")`. Real servers have shipped both bugs, and a silent infinite loop is the worst outcome.

### 5. Conversion: item type from `model=` or `Iterator[...]`

The page request itself must not be converted, because the annotation describes items, not `data`. The builder passes `model=Any` for the page request, which `converter_for` treats as "no conversion". The item converter comes from:
- `model=` (the item type), or
- the return annotation `Iterator[X]`, `Iterable[X]`, `AsyncIterator[X]` or `Generator[X, ...]`, built with the existing `converter_for(X)` (pydantic or dataclass).

Any other annotation, such as `-> list` or none, means items stay dicts. A string annotation that can't be resolved yet is resolved on first use, as `DeferredConverter` does today.

### 6. Codegen: a client-side `@paginate` directive

```graphql
query Issues($owner: String!, $name: String!, $after: String) {
  repository(owner: $owner, name: $name) {
    issues(first: 50, after: $after) @paginate {
      pageInfo { hasNextPage endCursor }
      nodes { number title }
    }
  }
}
```
- **Reading it:** the collector finds `@paginate` on a field of the operation itself (not inside fragments), removes it from the AST before validation and printing, and records the path of response keys to that field. The directive isn't in the server's schema, so it never reaches validation or the wire.
- **Problems,** reported as `file:line:column` with the others:
  - more than one `@paginate` in an operation;
  - `@paginate` inside a fragment;
  - no `$after` variable;
  - the field's selection lacks unaliased `pageInfo { hasNextPage endCursor }`, or `nodes`/`edges { node }`. This is checked by collecting the field's selection (fragments included) against its schema type.
- **The `ApiDefinition`:** `GraphQLOperationSpec.paginate` holds the path. `Operation.response` is the item model, found by walking the result models along the path to the connection model's `nodes` item, or its `edges` item's `node`. `response_plain` is `dict[str, Any]`, and the operation is marked as paginated.
- **Emitters:** the dict method gets `paginate="repository.issues"` and returns `Iterator[dict[str, Any]]`. The typed method returns `Iterator[IssuesRepositoryIssuesNodes]` and calls `self._paginate("issues", "IssuesRepositoryIssuesNodes", ...)`. Both import `Iterator` from `collections.abc`. The whole result model is still generated, because the connection's models are where the item model lives.

*Alternative:* detect connections automatically, as any field with `pageInfo` plus `nodes`. Rejected because it would change the return types of existing generated methods, which is a breaking change in generated code, and some callers want one page (with `totalCount`), not all items.

### 7. `TypedClient._paginate`

`_paginate(route_name, item_type, *args, **kwargs)` calls the dict route with plain arguments, like `_call`, and returns a generator that validates each item with the cached `TypeAdapter` as it's yielded. On an async parent it returns an async generator. The validation is lazy, matching the lazy paging.

## Risks / Trade-offs

- **[Errors surface on iteration, not on the call]** (generators are lazy) → This is documented, and it's standard for Python iterators. Callers wanting an eager list write `list(...)`.
- **[Annotations say `Iterator`, while `.aio` returns an async iterator]** → This is the same as today's `.aio` returning coroutines for methods annotated with plain types. It's documented.
- **[A connection without `first`, or with a huge `first`, is the server's business]** → Page size stays in the operation.
- **[`@paginate` is an apiroute-specific directive in `.graphql` files]** → Editors may flag it as unknown. It's documented, and it's removed before anything else sees the document.

## Open Questions

- Should a later change expose page-level data (e.g. `totalCount`) through a `pages=True` mode that yields whole pages?
