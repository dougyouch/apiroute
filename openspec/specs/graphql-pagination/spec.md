# graphql-pagination Specification

## Purpose
TBD - created by archiving change add-graphql-pagination. Update Purpose after archive.
## Requirements
### Requirement: A route can iterate a connection across pages
`graphql_route(..., paginate="a.b")` SHALL make the method return an iterator over the items of the Relay connection at that dotted path inside `data`, across all pages. Items SHALL be the connection's `nodes` elements, or else each `edges` element's `node`. The next page SHALL be requested only when iteration reaches it, with the previous page's `pageInfo.endCursor` passed as the cursor variable (`$after` by default, or the variable `cursor=` names). Iteration SHALL stop when `pageInfo.hasNextPage` is false. Every page SHALL be an ordinary request, with the client's headers, hooks, retries and GraphQL error handling.

#### Scenario: Three pages
- **WHEN** a route with `paginate="repository.issues"` is iterated, and the server answers three pages of two issues, the first two with `hasNextPage: true` and cursors `c1` and `c2`
- **THEN** six items are yielded in order, and the requests carry `after` unset, then `"c1"`, then `"c2"`

#### Scenario: Lazy paging
- **WHEN** a caller takes only the first item with `next()`
- **THEN** only one request has been sent

#### Scenario: Edges
- **WHEN** the connection selects `edges { node { ... } }` instead of `nodes`
- **THEN** each edge's `node` is yielded

#### Scenario: Starting from a cursor
- **WHEN** the caller passes `after="c5"`
- **THEN** the first request carries `after: "c5"`

#### Scenario: A null connection
- **WHEN** a page's data has `{"repository": null}` along the path
- **THEN** iteration ends without yielding and without error

#### Scenario: Errors on a later page
- **WHEN** the second page answers with GraphQL `errors`
- **THEN** iteration raises `GraphQLError` after yielding the first page's items

### Requirement: Paginated routes are checked
Creating the class SHALL raise `RouteDefinitionError` when the operation doesn't declare the cursor variable, or when `data=` is combined with `paginate=`. During iteration, a page whose connection lacks `pageInfo.hasNextPage`/`pageInfo.endCursor`, or lacks both `nodes` and `edges`, SHALL raise `ValueError` naming the operation and what it must select. So SHALL a page that answers `hasNextPage: true` with a null `endCursor` or with the same cursor as the previous page.

#### Scenario: No cursor variable
- **WHEN** `graphql_route("query Q { viewer { repositories(first: 5) { ... } } }", paginate="viewer.repositories")` is declared
- **THEN** creating the class raises `RouteDefinitionError` mentioning `$after`

#### Scenario: Missing pageInfo
- **WHEN** a page's connection has `nodes` but no `pageInfo`
- **THEN** iteration raises `ValueError` saying the operation must select `pageInfo { hasNextPage endCursor }`

#### Scenario: Repeated cursor
- **WHEN** two consecutive pages both answer `hasNextPage: true` with `endCursor: "c1"`
- **THEN** iteration raises `ValueError` saying it would page forever

### Requirement: Items are converted to the item type
Items SHALL be converted by `model=` when given, else by `X` from a return annotation of `Iterator[X]`, `Iterable[X]`, `AsyncIterator[X]` or `Generator[X, ...]`, using pydantic or dataclass conversion as for other routes. Otherwise items SHALL stay dicts. The page request's `data` itself SHALL NOT be converted.

#### Scenario: Dataclass items
- **WHEN** a paginated route is annotated `-> Iterator[Issue]`, where `Issue` is a dataclass
- **THEN** each yielded item is an `Issue`

### Requirement: Async iteration
Through `.aio`, a paginated route SHALL return an async iterator with the same paging, requesting each page as iteration reaches it.

#### Scenario: Async for
- **WHEN** `async for issue in client.aio.issues(...)` runs over two pages
- **THEN** every item of both pages is yielded

### Requirement: Generated clients paginate with @paginate
In an operation file, a `@paginate` directive on a connection field SHALL make the generated method paginate along the response-key path to that field. The directive SHALL be removed from the document that's validated and sent. The generator SHALL report, as `file:line:column` problems that stop generation:
- more than one `@paginate` in an operation;
- `@paginate` inside a fragment;
- an operation that doesn't declare `$after`;
- a connection selection without unaliased `pageInfo { hasNextPage endCursor }` and `nodes` or `edges { node }`.

The dict method SHALL return `Iterator[dict[str, Any]]`. With `--models`, the typed method SHALL return `Iterator[<item model>]` and validate each item as it's yielded.

#### Scenario: Generated pagination
- **WHEN** `issues(first: 50, after: $after) @paginate { pageInfo { hasNextPage endCursor } nodes { number } }` is inside `repository` in `query Issues(...)`
- **THEN** the generated `issues` route has `paginate="repository.issues"`, its sent document has no `@paginate`, and `client.models.issues(...)` yields `IssuesRepositoryIssuesNodes` items across pages

#### Scenario: Aliased connection
- **WHEN** the paginated field is aliased `open: issues(...) @paginate`
- **THEN** the route's path is `repository.open`

#### Scenario: Missing pageInfo in a generated operation
- **WHEN** the `@paginate` field selects `nodes { number }` without `pageInfo`
- **THEN** generation fails with the field's file, line and column, saying it must select `pageInfo { hasNextPage endCursor }`

#### Scenario: Other operations are unchanged
- **WHEN** a package is generated from operations that don't use `@paginate`
- **THEN** its files are identical to those generated before this change

