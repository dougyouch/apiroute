## Context

GraphQL routes already paginate: `graphql_route(..., paginate="repository.issues")` returns a lazy iterator. `GraphQLPaginator` calls the bound route once per page, adding the cursor variable through `RequestOptions(body=...)`. REST routes have the pieces a paginator needs but no paginator:
- `RequestOptions` merges `query` and `body` over a call;
- `returns="response"` hands back the `httpx.Response`, so headers such as `Link` can be read;
- the executor applies the client's headers, hooks, retries, idempotency keys and `check_response` to every request.

The REST paging styles seen in the client repositories:

| API | Style | Items | Stop |
| --- | --- | --- | --- |
| Stripe | `starting_after=<last item id>` | `data` | `has_more: false` |
| GitHub REST | `Link: <…>; rel="next"` | the body (an array), or `items` for search | no `next` link |
| eBay REST | `next` URL in the body (offset/limit underneath) | varies (`inventoryItems`, `orders` …) | no `next` |
| Slack / Google / Notion | `next_cursor` / `nextPageToken` / `next_cursor` | `members`, `items`, `results` | empty or missing token |
| Older APIs | `page`, `per_page` | the body or a key | empty or short page, `total_pages` |
| Elasticsearch-style | `offset`, `limit` | a key | short page, `total` |

## Goals / Non-Goals

**Goals:**
- One paginator and one strategy protocol, covering the styles above with five built-in strategies and leaving room for custom ones.
- The same caller experience as GraphQL pagination: lazy, sync and async, typed items, an ordinary request per page.
- Safe by default: explicit stop signals, no infinite loops, no credentials sent to another host.
- Generated clients gain paginated methods without changing existing ones, driven by explicit rules or a vendor extension.

**Non-Goals:**
- Guessing pagination without rules. A wrong guess silently drops or repeats data; shape-matching rules make the same inference explicit and reviewable.
- Parallel page fetching, prefetching, or resuming an interrupted iteration from saved state (a caller can start from a cursor or page argument).
- Consistency under concurrent writes (offset and page skew). That's the API's property, and it's documented, not solved.
- Changing GraphQL pagination.

## Decisions

### One paginator, strategies as small objects
A strategy answers two questions per page: `items(page)` (a list) and `next(page)` (a `NextRequest` or `None`). A `Page` carries:
- the decoded body;
- the `httpx.Response`;
- what was sent (the query and body overrides, or the URL);
- the page's index.

A `NextRequest` holds `query` and `body` overrides (merged over the caller's arguments), or a `url` that replaces the request's URL entirely.
- **Why:** cursor, page and offset APIs differ only in `next()`. Two iterator types (the original idea of a cursor iterator plus a page iterator) would duplicate the loop, `.pages()`, async, conversion and the guards.
- **Alternative:** a configuration-only schema (like Speakeasy's) with no code hook. That's rejected: real APIs have quirks (a cursor in a header, a token at a nested path), and a two-method protocol handles them in a few lines.

### Built-in strategies and their stop rules

The page-number strategy is `PageNumber`, since `Page` is the page object strategies receive.

| Strategy | Next request | Stops when |
| --- | --- | --- |
| `Cursor(param, token="next_cursor", header=None, items=…, location="query")` | `{param: token}` from a dotted path in the body, or from a header | the token is missing, null or `""` |
| `ItemCursor(param="starting_after", field="id", has_more="has_more", items="data")` | `{param: last_item[field]}` | `has_more` is false; an empty page with `has_more` true is an error |
| `NextUrl(link="next", path=None, items=…)` | the URL in the `Link` header's `rel` (default `next`), or at a dotted body path | no such URL |
| `PageNumber(param="page", start=1, size=None, total_pages=None, items=…)` | `{param: n + 1}` | an empty page; a short page when `size` names the page-size parameter and the caller set it; or `n` reaching `total_pages` |
| `Offset(param="offset", limit="limit", total=None, items=…)` | `{param: offset + len(items)}` | an empty page; a short page when the limit is known; or the offset reaching `total` |

- `items` is a dotted path, or `""` for a body that is itself the list (the default).
- An explicit signal (`has_more`, a token, a URL, a total) always wins over the empty-page and short-page rules. `Page` and `Offset` use the heuristics only when the API gives no total. That's because a server may cap the page size below what was asked, which would make a short page look like the last one.

### Paging is built on the existing route call
`RouteMethod.bind` wraps a `paginate=` route as `GraphQLRouteMethod` wraps its routes:
- The first page is the call as made: the caller's arguments, including a starting cursor or page.
- Each later page is the same bound call with `RequestOptions(query=…, body=…, url=…, returns="response")` merged in.
- The paginator decodes the JSON itself from the response, so it sees headers as well as the body.
- **Why:** every page gets the client's auth, `on_request`, retries, idempotency keys, `check_response` and logging for free.
- **Added:** `RequestOptions` gains `url`, an absolute URL replacing base URL, path and query. `NextUrl` URLs already carry the query.

### Foreign next URLs are refused
A next URL whose scheme, host and port differ from the base URL's raises `ValueError` before anything is sent. A relative URL resolves against the base URL.
- **Why:** the client's `Authorization` header goes on every page, and a hostile or misconfigured `Link` header must not collect it.

### Loop guards
- Paging raises `ValueError` naming the operation when a cursor, page token or next URL repeats the previous one.
- `ItemCursor` and `Cursor` raise when a page says there's more but gives nothing to continue from.
- **Why:** these are API bugs, and failing loudly beats spinning forever or quietly stopping. That's the same policy as GraphQL's repeated `endCursor`.

### The iterator object
A paginated call returns a `Paginated` object:
- Iterating it yields items.
- `.pages()` yields `Page` objects.
- Through `.aio`, both are async iterators.

Nothing is requested until iteration starts, and a later page only when iteration reaches it. Capping uses Python's own tools (`islice`, `break`), so there's no `max_items` argument to collide with an API parameter of the same name.

### Item conversion
As for GraphQL:
- `model=`, or the `X` of an `Iterator[X]` (and similar) return annotation, converts each item through the pydantic or dataclass converters.
- Otherwise items stay dicts.

Generated `.models` methods validate items through `TypedClient._paginate`, as GraphQL's typed methods already do.

### Generated `_all` methods, not a changed `list`
A matched operation keeps its one-page method and gains `<method>_all` (`customers.list_all`, `issues.list_for_repo_all`).
- **Why:** changing `list` to iterate would break every generated client and remove one-page access, which callers need for "first N" and UI paging.
- **Rejected:** a `.all()` method on the one-page result, which needs a result wrapper type the dict layer doesn't have.

The suffix is fixed in this change. If a spec already has a method by that name, the generator reports a clash.

### Codegen rules
`--pagination FILE` (JSON, or YAML with the `codegen` extra) holds an ordered list of rules. A rule selects operations, and the first matching rule wins:
- `operations`: operation IDs, or glob patterns;
- `method`: HTTP methods, default `GET`;
- `has_parameter`: parameter names;
- `response`: `"array"` or `{"has": [property names]}`.

It gives the strategy: `type` (`cursor`, `item_cursor`, `next_url`, `page`, `offset`) and the strategy's arguments, `items` included. When `items` names a response property, the item type is that array's item schema. When it's omitted, the response must be an array (its item schema), or have exactly one array property, which is used.

Without a rule, an operation with `x-speakeasy-pagination` is mapped:
- `offsetLimit` becomes `Offset`, or `PageNumber` when `inputs` name a page;
- `cursor` becomes `Cursor`;
- `url` becomes `NextUrl` (body path).

Its `outputs.results` JSONPath (`$.data`) becomes `items`.

Example rules for Stripe and GitHub:

```yaml
- has_parameter: [starting_after]
  response: {has: [data, has_more]}
  paginate: {type: item_cursor, param: starting_after, items: data}
- response: array
  has_parameter: [page]
  paginate: {type: next_url}          # GitHub: Link header
```

### Emission
The dict emitter writes the `_all` route with the same signature as its one-page method, with `paginate=ItemCursor(...)` (a constructor call with literal arguments) and return type `Iterator[dict[str, Any]]`. The typed emitter writes `Iterator[ItemModel]` through `_paginate`. Strategies are imported from `apiroute.pagination` only in modules that use them.

## Risks / Trade-offs

- **[Offset and page drift when data changes mid-iteration]** → Documented. Cursor strategies are recommended where the API offers them.
- **[A server capping page size makes a short page look final]** → Explicit signals take precedence. The short-page rule applies only when the caller set the size parameter, and the README warns about it.
- **[Rules match more operations than intended]** → Rules are explicit and ordered. The generator prints how many operations each rule matched, and warns about a rule that matched none. A generated `_all` method is additive, so a wrong match adds a method that fails loudly rather than changing an existing one.
- **[`returns="response"` bypasses response models]** → The paginator applies the item path and item conversion itself, and a paginated route can't also set `returns=`, `stream=`, `decoder=` or a `Result` parameter (a `RouteDefinitionError`).
- **[Large `max` loops on very big lists]** → It's lazy by design. The README shows `islice` for capping.
- **[`x-speakeasy-pagination` dialect differences]** → Only the documented `offsetLimit`, `cursor` and `url` types are mapped. Anything else is a generator warning, and the operation gets no `_all` method.

## Migration Plan

Additive. It releases as a minor version (`feat:`). Client repositories opt in afterwards:
- stripe-apiroute: a rules file for `ItemCursor`;
- github-apiroute: `NextUrl` via `Link`;
- eBay later: `NextUrl` from the body's `next`.

Each adds a live test that pages past the first page. Rolling back means removing the rules file, which removes the `_all` methods (a `feat!:` in that client repository if they were released).

## Open Questions

- ~~Is `_all` the right suffix?~~ Decided: `_all`.
- Should `ItemCursor` support backwards paging (`ending_before` with the first item)? Proposed: not now. The caller can call the one-page method with `ending_before`.
