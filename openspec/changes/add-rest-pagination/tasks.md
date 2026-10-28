## 1. Request plumbing

- [x] 1.1 Add `url` to `RequestOptions` (merged like the other fields), and have the request builder use it, absolute, in place of base URL, path and query
- [x] 1.2 Add a same-origin check helper: a URL resolved against the request URL, refused (`ValueError`) when its scheme, host or port differs from the base URL's
- [x] 1.3 Tests: a `url` override reaches the transport with the client's headers; relative URLs resolve; foreign hosts are refused before sending

## 2. Strategy protocol and pages

- [x] 2.1 `apiroute/pagination/` package: `Page` (data, response, request overrides or URL, index, items) and `NextRequest` (query, body, url), one class per file
- [x] 2.2 Dotted-path reader shared by the strategies (missing keys give None; a non-list `items` raises `ValueError` naming the path)
- [x] 2.3 `Link` header `rel` lookup (httpx's `response.links`)
- [x] 2.4 Tests for the path reader and the Link parser

## 3. Built-in strategies

- [x] 3.1 `Cursor` (body path or header token; query or body location; stops on missing, null, "")
- [x] 3.2 `ItemCursor` (last item's field; `has_more`; empty page with more is an error)
- [x] 3.3 `NextUrl` (Link rel or body path)
- [x] 3.4 `PageNumber` (start, `total_pages` path, short-page rule only with `size` and no total)
- [x] 3.5 `Offset` (`total` path, short-page rule only with `limit` and no total)
- [x] 3.6 Unit tests per strategy against hand-built `Page` objects, covering every stop rule in the spec

## 4. The paginator and routes

- [x] 4.1 `RestPaginator`: the first page as called; later pages through the bound call with the merged `RequestOptions` (`returns="response"`); JSON decoded from the response; `Paginated` object with item iteration and `.pages()`, sync and async
- [x] 4.2 Loop guards: a repeated cursor, token, page or URL raises `ValueError` naming the operation
- [x] 4.3 `route(..., paginate=)` option; `RouteMethod.bind` wraps paginated routes (as `GraphQLRouteMethod` does); `RouteDefinitionError` for `paginate=` with `returns=`, `stream=`, `decoder=` or a `Result` parameter
- [x] 4.4 Item conversion from `model=` or an `Iterator[X]`-style annotation, sharing GraphQL's item-converter logic
- [x] 4.5 `TypedClient._paginate` works for REST `_all` methods (items validated as yielded)
- [x] 4.6 Route tests for every spec scenario: lazy paging, filters on every page, starting cursor, errors and retries on later pages, idempotency keys on POST pages, async, conversion, custom strategy

## 5. Codegen

- [ ] 5.1 `Operation.pagination` in the API definition (strategy type, arguments, item type)
- [ ] 5.2 Rules loader (`--pagination FILE`, JSON or YAML): rule matching by operation ID glob, method, parameters and response shape; first match wins; per-rule match counts and warnings; errors for unknown types or arguments
- [ ] 5.3 `x-speakeasy-pagination` reader for `offsetLimit`, `cursor` and `url`, with warnings for anything else
- [ ] 5.4 Item type resolution from the `items` path (array item schema, or the response's own array), with an error when the path isn't an array
- [ ] 5.5 Dict emitter: `<name>_all` route with the same parameters, `paginate=<Strategy>(...)`, `Iterator[dict[str, Any]]`, and the `apiroute.pagination` import only when used; a clash with an existing name is an error
- [ ] 5.6 Typed emitter: `<name>_all` through `_paginate` returning `Iterator[<item model>]`
- [ ] 5.7 Codegen tests: a fixture spec with Stripe-, GitHub- and offset-style operations and one with `x-speakeasy-pagination`; generated packages paginate over a mock transport; output passes ruff and the mypy typing test; existing fixtures' output is unchanged

## 6. Docs and release

- [ ] 6.1 README: a REST pagination section (strategies, `.pages()`, async, `islice` for caps, the stop rules and their caveats, custom strategies) and the `--pagination` rules in the codegen notes
- [ ] 6.2 Client-repository skill: a `pagination:` entry in `apis.yaml` and how `generate.py` passes it
- [ ] 6.3 Full suite, the lowest-dependencies run, ruff; then open the PR (`feat:`)

## 7. Proving it on real APIs (after release, in the client repositories)

- [ ] 7.1 stripe-apiroute: a rules file for `ItemCursor` on list operations; a live test paging customers past the first page with `limit=1`
- [ ] 7.2 github-apiroute: `NextUrl` via `Link` for array list operations with `page`; a live test paging a public repo's issues past the first page with `per_page=2`
