# rest-pagination Specification

## Purpose
Paginated REST routes: `route(..., paginate=<strategy>)` iterates the items of every page lazily, sync and async, through built-in strategies (`Cursor`, `ItemCursor`, `NextUrl`, `PageNumber`, `Offset`) or a custom one, with guards against endless paging and against next-page URLs on other hosts.
## Requirements
### Requirement: A REST route can iterate every page
`route(..., paginate=<strategy>)` SHALL make the method return an iterator over the items of every page. The first page SHALL be requested with the caller's arguments as given. Each later page SHALL be requested only when iteration reaches it, with the strategy's next request applied: query or body values merged over the caller's arguments, or a URL replacing the request's URL. The caller's other arguments (filters, page size) SHALL be kept on every page. Every page SHALL be an ordinary request, with the client's headers, `on_request`, retries, idempotency keys and `check_response`.

#### Scenario: Three pages
- **WHEN** a route with `paginate=ItemCursor()` is iterated, and the server answers `{"data": [a, b], "has_more": true}`, then `{"data": [c, d], "has_more": true}`, then `{"data": [e], "has_more": false}`
- **THEN** a, b, c, d and e are yielded in order, and the requests carry no `starting_after`, then `starting_after=<b.id>`, then `starting_after=<d.id>`

#### Scenario: Lazy paging
- **WHEN** a caller takes only the first item with `next()`
- **THEN** only one request has been sent

#### Scenario: Filters stay on every page
- **WHEN** the caller passes `limit=2, status="open"`
- **THEN** every page's request carries `limit=2&status=open`

#### Scenario: Starting from a cursor
- **WHEN** the caller passes `starting_after="cus_9"`
- **THEN** the first request carries `starting_after=cus_9`

#### Scenario: An error on a later page
- **WHEN** the second page answers 500 and retries are off
- **THEN** iteration raises `UnexpectedResponse` after yielding the first page's items

#### Scenario: Retries cover each page
- **WHEN** retries allow two attempts, and the second page answers 503 once (retried by `should_retry`) and then succeeds
- **THEN** iteration yields every item of all pages

### Requirement: Built-in strategies
apiroute SHALL provide these strategies in `apiroute.pagination`. Each SHALL take `items`, a dotted path to the page's list of items, where `""` (the default) means the body is the list.

- `Cursor(param, token="next_cursor", header=None, location="query")`: the next request SHALL set `param`, in the query or (`location="body"`) the body, to the token read from the body's dotted path `token`, or from response header `header` when given. Paging SHALL stop when the token is missing, null or `""`.
- `ItemCursor(param="starting_after", field="id", has_more="has_more", items="data")`: the next request SHALL set `param` to the last item's `field`. Paging SHALL stop when the body's `has_more` is false.
- `NextUrl(link="next", path=None)`: the next request SHALL go to the URL in the `Link` header entry whose `rel` is `link`, or, when `path` is given, to the URL at that dotted body path. Paging SHALL stop when there is none.
- `PageNumber(param="page", start=1, size=None, total_pages=None)`: the next request SHALL set `param` to the page number plus one. Paging SHALL stop:
  - at an empty page;
  - when `total_pages` names a body path and the page number has reached it;
  - or, only when no total is given, at a page shorter than the caller's value of the `size` parameter.
- `Offset(param="offset", limit="limit", total=None)`: the next request SHALL set `param` to the previous offset plus the number of items received. Paging SHALL stop:
  - at an empty page;
  - when `total` names a body path and the new offset has reached it;
  - or, only when no total is given, at a page shorter than the caller's value of `limit`.

#### Scenario: A cursor in the body
- **WHEN** `Cursor("cursor", token="response_metadata.next_cursor", items="members")` pages a response with `next_cursor: "dXNlcg=="` and then `next_cursor: ""`
- **THEN** the second request carries `cursor=dXNlcg==`, and paging stops after it

#### Scenario: A cursor in a header
- **WHEN** `Cursor("page_token", header="X-Next-Token")` pages a response whose header is `X-Next-Token: t2`
- **THEN** the second request carries `page_token=t2`

#### Scenario: A cursor in the body of a POST search
- **WHEN** `Cursor("cursor", location="body")` pages a POST route whose body is `{"query": "x"}`
- **THEN** the second request's body is `{"query": "x", "cursor": "<token>"}`

#### Scenario: GitHub's Link header
- **WHEN** `NextUrl()` pages a response with `Link: <https://api.github.com/repositories/1/issues?page=2>; rel="next", <…?page=5>; rel="last"`
- **THEN** the second request goes to `https://api.github.com/repositories/1/issues?page=2`, and paging stops at a response with no `rel="next"`

#### Scenario: A next URL in the body
- **WHEN** `NextUrl(path="next", items="results")` pages `{"results": [...], "next": "https://api.test/items?cursor=2"}` and then `{"results": [...], "next": null}`
- **THEN** two pages are requested

#### Scenario: Pages with a total
- **WHEN** `PageNumber(total_pages="meta.pages", items="data")` pages responses with `meta.pages: 3`
- **THEN** pages 1, 2 and 3 are requested, and no fourth

#### Scenario: Pages without a total
- **WHEN** `PageNumber(size="per_page")` pages with the caller's `per_page=2`, and the third page has one item
- **THEN** paging stops after the third page

#### Scenario: Offsets
- **WHEN** `Offset(total="total", items="hits")` pages a total of 5 with `limit=2`
- **THEN** the requests carry `offset` unset, then `offset=2`, then `offset=4`, and paging stops

### Requirement: Custom strategies
A strategy SHALL be any object with `items(page) -> list` and `next(page) -> NextRequest | None`. A `Page` SHALL give:
- the decoded JSON body (`data`);
- the `httpx.Response` (`response`);
- the query and body overrides or the URL that produced it;
- its zero-based `index`.

A `NextRequest` SHALL carry `query` and `body` mappings to merge, or a `url`. Built-in strategies SHALL be instances of the same protocol.

#### Scenario: A strategy reading a header and the body
- **WHEN** a custom strategy returns `NextRequest(query={"since": page.data["last_seen"]})` until `page.response.headers["X-Done"] == "1"`
- **THEN** the route pages with those values and stops when that header appears

### Requirement: Pages and items
Iterating the returned object SHALL yield items. `.pages()` SHALL yield the `Page` objects, with `items` already extracted. Nothing SHALL be requested before iteration starts.

#### Scenario: Whole pages
- **WHEN** `.pages()` of a two-page iteration is listed
- **THEN** two `Page` objects are returned, each with its items, body and response

### Requirement: Async iteration
Through `.aio`, a paginated route SHALL return an object that `async for` iterates over items, and whose `.pages()` is an async iterator. Each page SHALL be requested when iteration reaches it.

#### Scenario: Async for
- **WHEN** `async for customer in client.aio.list_all(...)` runs over two pages
- **THEN** every item of both pages is yielded, from two requests

### Requirement: Items are converted to the item type
Items SHALL be converted by `model=` when given, else by `X` from a return annotation of `Iterator[X]`, `Iterable[X]`, `AsyncIterator[X]` or `Generator[X, ...]`, with the pydantic or dataclass converters. Otherwise items SHALL stay as decoded. A paginated route reads JSON pages itself, so it SHALL NOT also set `returns=` (other than `"json"`), `stream=`, `decoder=` or a `Result` parameter, and creating the class SHALL raise `RouteDefinitionError` when it does.

#### Scenario: Dataclass items
- **WHEN** a paginated route is annotated `-> Iterator[Customer]`, where `Customer` is a dataclass
- **THEN** each yielded item is a `Customer`

#### Scenario: returns= with paginate=
- **WHEN** a route declares both `paginate=ItemCursor()` and `returns="text"`
- **THEN** creating the class raises `RouteDefinitionError`

### Requirement: Paging can't loop or leak credentials
Iteration SHALL raise `ValueError`, naming the operation:
- when a strategy's next cursor, token, page or URL equals the one that produced the current page;
- when `ItemCursor` meets an empty page that says there's more;
- when a page's `items` path is missing or isn't a list.

A next URL SHALL resolve against the request's URL. One whose scheme, host or port differs from the client's base URL SHALL raise `ValueError` before any request is sent to it.

#### Scenario: A repeated cursor
- **WHEN** two consecutive pages both give `next_cursor: "c1"`
- **THEN** iteration raises `ValueError` saying it would page forever

#### Scenario: A next URL on another host
- **WHEN** a `Link` header's next URL is `https://evil.test/steal?page=2` for a client whose base URL is `https://api.github.com`
- **THEN** iteration raises `ValueError`, and no request goes to `evil.test`

#### Scenario: A relative next URL
- **WHEN** a body's `next` is `/v1/items?cursor=2`
- **THEN** the next request goes to that path on the base URL's host

#### Scenario: Items not a list
- **WHEN** `items="data"` and a page's `data` is an object
- **THEN** iteration raises `ValueError` naming the path

