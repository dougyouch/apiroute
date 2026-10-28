## Why

Every real REST API pages its lists, and each does it differently:
- Stripe: `has_more` and `starting_after` set to the last item's id;
- GitHub: a `Link` header with `rel="next"`;
- Slack: `response_metadata.next_cursor`;
- older APIs: `page` and `per_page`.

apiroute can page GraphQL connections (`paginate="a.b"`), but a REST route returns one page, so callers of the generated Stripe, GitHub and eBay clients write the paging loop themselves. Those loops are easy to get subtly wrong: stopping on a short page, losing filters on the next request, or looping forever on a repeated cursor. The loop is the same shape for every API (request, items, next request or stop). Only the "next request" step differs, so one paginator with pluggable strategies can cover nearly all of them.

## What Changes

- **`route(..., paginate=<strategy>)`** makes a REST route return an iterator over the items of every page, fetched lazily, as GraphQL's `paginate=` does. Each page is an ordinary request through the client's headers, hooks, retries and error handling, with the caller's own arguments (filters, page size) kept on every page.
- **Built-in strategies:**
  - `Cursor`: a token from the body or a header goes into a query or body parameter;
  - `ItemCursor`: a field of the last item (Stripe's `starting_after`), with a `has_more` flag;
  - `NextUrl`: a URL from the `Link` header or a body field;
  - `PageNumber`: page numbers;
  - `Offset`: offset and limit.

  Each says where the items are (a dotted path, or the body itself) and how it knows it's done. A custom strategy implements the same two-method protocol.
- **The iterator** yields items. `.pages()` yields whole pages (items, decoded body, the `httpx.Response`). It works through `.aio` as an async iterator. A typed route converts each item, as GraphQL pagination does. `itertools.islice` caps it as usual.
- **Safety:**
  - An explicit stop signal is used whenever the API gives one.
  - Paging stops with `ValueError` on a repeated cursor or URL, rather than looping.
  - A next URL on another host than the client's `base_url` is refused, so credentials are never sent elsewhere.
- **Code generation:**
  - `apiroute generate openapi --pagination FILE` takes rules that pick operations (by operation ID, or by shape: "has a `starting_after` parameter", "returns an array") and give their strategy.
  - Operations carrying `x-speakeasy-pagination` are paginated from that extension, with no rules needed.
  - Each matched operation keeps its one-page method and gains a paginated sibling, `<method>_all` (for example `customers.list_all`). The dict layer yields dicts, and `.models` yields the item model.
- No breaking changes: existing routes and generated methods keep their signatures and return types.

## Capabilities

### New Capabilities
- `rest-pagination`: paginated REST routes: the `paginate=` option, the built-in strategies and the strategy protocol, item extraction and conversion, `.pages()`, async iteration, stop rules and the guards against loops and foreign next URLs.
- `rest-pagination-codegen`: generating paginated methods: the `--pagination` rules file, `x-speakeasy-pagination`, the `<method>_all` variants in both layers, and the item types they yield.

### Modified Capabilities
<!-- None: GraphQL pagination and existing routes keep their behaviour. -->

## Impact

- **Runtime:** a new `apiroute.pagination` package (the strategies and the paginator). `RouteMethod.bind` returns an iterator for `paginate=` routes. Route options gain `paginate`. `RequestOptions` gains a `url` override, used for next URLs.
- **Codegen:**
  - the OpenAPI reader records each operation's pagination;
  - a rules loader and an `x-speakeasy-pagination` reader;
  - both client emitters write the `_all` variants;
  - the CLI gets `--pagination`.
- **Docs:** README sections for REST pagination and for the codegen rules. The client-repository skill gets a `pagination:` entry in `apis.yaml`.
- **Downstream, after release:** stripe-apiroute (`ItemCursor` on every list operation) and github-apiroute (`NextUrl` from `Link` on list operations) adopt it, with live tests paging past the first page. These are follow-up changes in those repositories.
- **Dependencies:** none new. Rules files may be JSON, or YAML when pyyaml (the `codegen` extra) is installed.
