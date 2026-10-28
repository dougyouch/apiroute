# rest-pagination-codegen Specification

## Purpose
Generated paginated methods: `--pagination` rules and `x-speakeasy-pagination` give matched OpenAPI operations a `<name>_all` method in both the dict and typed layers, yielding each page's items as the item type.
## Requirements
### Requirement: Pagination rules pick operations and their strategy
`apiroute generate openapi --pagination FILE` SHALL read an ordered list of rules from a JSON file, or a YAML file when pyyaml is installed. A rule SHALL select operations by any combination of:
- `operations` (operation IDs or glob patterns);
- `method` (HTTP methods, default `["GET"]`);
- `has_parameter` (parameter names the operation must have);
- `response` (`"array"`, or `{"has": [...]}` naming properties the success response must have).

A rule SHALL give `paginate`, with a `type` (`cursor`, `item_cursor`, `next_url`, `page`, `offset`) and that strategy's arguments. Each operation SHALL take the first rule that matches. The generator SHALL print how many operations each rule matched, and warn about a rule that matched none. An unknown `type` or argument SHALL stop generation with an error naming the rule.

#### Scenario: Stripe-style rule
- **WHEN** a rule has `has_parameter: [starting_after]`, `response: {has: [data, has_more]}` and `paginate: {type: item_cursor, items: data}`
- **THEN** every list operation with `starting_after` and that response gets a paginated method using `ItemCursor(items="data")`, and other operations don't

#### Scenario: First match wins
- **WHEN** two rules match an operation
- **THEN** it uses the first rule's strategy

#### Scenario: A rule matching nothing
- **WHEN** a rule's `operations: [Nope*]` matches no operation
- **THEN** generation succeeds with a warning naming the rule

### Requirement: x-speakeasy-pagination is honoured
An operation with no matching rule that carries `x-speakeasy-pagination` SHALL be paginated from it:
- `type: offsetLimit` becomes `Offset`, or `PageNumber` when its inputs name a `page` parameter;
- `type: cursor` becomes `Cursor`;
- `type: url` becomes `NextUrl` with the body path of `outputs.nextUrl`.

`outputs.results` (a `$.`-rooted JSONPath of dotted keys) SHALL become `items`. Any other type, or a JSONPath beyond dotted keys, SHALL be a warning, and the operation SHALL get no paginated method.

#### Scenario: An offsetLimit extension
- **WHEN** an operation has `x-speakeasy-pagination: {type: offsetLimit, inputs: [{name: offset, in: parameters, type: offset}, {name: limit, in: parameters, type: limit}], outputs: {results: $.data.items}}`
- **THEN** its paginated method uses `Offset(param="offset", limit="limit", items="data.items")`

### Requirement: Paginated operations get an _all method in both layers
A paginated operation SHALL keep its one-page method unchanged and gain `<name>_all` in the same section, with the same parameters. The `_all` route SHALL use `paginate=` with the operation's strategy. The dict method SHALL return `Iterator[dict[str, Any]]`. With `--models`, the typed method SHALL return `Iterator[<item model>]` and validate each item as it's yielded. The item model SHALL be the item schema of the array at `items` in the success response, or of the response itself when `items` is `""`. When `<name>_all` already exists in the section, generation SHALL stop with an error naming both operations. Generated modules SHALL import strategies from `apiroute.pagination` only when they use one, and SHALL pass `ruff check` and `ruff format`.

#### Scenario: Stripe's customers
- **WHEN** Stripe's spec is generated with the Stripe rule and `--operation-names`
- **THEN** `stripe.customers.list` still returns one page, and `stripe.customers.models.list_all(limit=100)` yields `Customer` models across pages

#### Scenario: GitHub's issues
- **WHEN** GitHub's REST spec is generated with `response: array`, `has_parameter: [page]`, `paginate: {type: next_url}`
- **THEN** `gh.issues.list_for_repo_all("o", "r")` follows `Link` headers and yields issue dicts

#### Scenario: Item type of an array response
- **WHEN** a paginated operation's success response is `type: array, items: {$ref: Issue}`
- **THEN** the typed `_all` method returns `Iterator[Issue]`

#### Scenario: An items path that isn't an array
- **WHEN** a rule's `items: data` names a property that isn't an array in an operation's response
- **THEN** generation stops with an error naming the operation and the path

#### Scenario: A name clash
- **WHEN** a spec already has an operation named `list_all` in a section where `list` is paginated
- **THEN** generation stops with an error naming both operations

