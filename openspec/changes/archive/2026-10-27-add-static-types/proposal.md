## Why

apiroute ships `py.typed`, and generated clients come with pydantic models, but a type checker sees nothing a caller uses. Checking generated and hand-written clients with mypy 1.13 and pyright 1.1.390 showed `Any` everywhere:
- `client.get_user("x")` is `Any`;
- `client.pets.models.get_pet(1)` is `Any`;
- `client.get_user(123, extra=True)` isn't flagged.

Editors (Pylance is pyright) offer no completions or checks past the client object. There are three causes:
- `RouteMethod.__get__` returns `Any`, which erases every decorated method's signature;
- generated sections and `.models` are `lazy(...)` attributes, typed `Any`;
- nested `Section` classes are swapped for a descriptor at run time, which type checkers don't see.

mypy also reports `empty-body` on every route whose return type isn't `None`, because a route's body is just `...`.

## What Changes

- **Routes keep their signatures.** `RouteMethod` becomes generic over the decorated function's parameters and return type (`ParamSpec`, Python 3.10+). Through an instance, a route is typed as the method's own signature without `self`, so `client.get_user` is `(name: str) -> dict`. Wrong arguments and wrong uses of the result are flagged. The same applies to `graphql_route` on a `def`, including `paginate=` routes annotated `Iterator[...]`.
- **Routes without a `def`** (`get_user = route("/users/:name")`, or `graphql_route(...)` assigned) are typed as `Callable[..., Any]`, since their signature is generated at run time. They're accepted as before, without false errors.
- **Nested sections** (`class issues(Section)` inside a client) are typed as instances through a `__get__` on `Section`'s metaclass, which is only for type checkers; run-time behavior is unchanged. pyright and Pylance see `client.issues` as an `issues` instance with typed routes. mypy doesn't honour a metaclass `__get__`, so there the nested section's routes stay `Any`, as today, with no false errors.
- **Generated clients** annotate their lazy attributes, `repos: ReposSection = lazy(...)` and `models: HubApiModels = lazy(...)`, importing those classes under `TYPE_CHECKING` only, so loading stays lazy. Each generated `client.py` also starts with `# mypy: disable-error-code="empty-body"`. Typed calls (`client.repos.models.repository(...)`) return their pydantic models to type checkers too.
- **Sentinels type-check.** `FROM_CLIENT` is typed `Any`, so the documented `org: str = FROM_CLIENT` passes a type checker; today it's an "incompatible default". New **`FROM_RESPONSE`**: a keyword-only parameter defaulting to it receives the response (like a `Result`-annotated one), so its annotation can be the response's own type, and type checkers don't ask callers for it: `*, data: dict = FROM_RESPONSE`.
- **Generated routes always end with `...`,** after their docstring too. pyright rejects a docstring-only body ("must return value on all code paths") and accepts a stub body.
- **`TypedClient.with_options()`** returns the same class (`Self`-style). **`TypedClient.aio`** is typed `Any`: its methods return coroutines, which the sync annotations can't describe.
- **Typing tests** run mypy over sample code and a generated package, with `assert_type` and expected errors.

Not in scope: typing `.aio` and `with_options()` on clients (they stay `Any`, because their attribute types depend on each method), and a mypy plugin.

## Capabilities

### New Capabilities
- `static-types`: what type checkers see for routes, sections, generated clients and typed calls.

### Modified Capabilities
<!-- None: run-time behavior is unchanged. -->

## Impact

- **Runtime (annotations only, no behavior change):** `RouteMethod`, `RouteDecorator`, `GraphQLRouteMethod`/`GraphQLRouteDecorator`, `Section` (a metaclass with a typing-only `__get__`) and `TypedClient`.
- **Generated output changes:** a `TYPE_CHECKING` import block and annotations on lazy attributes, plus a mypy header comment, in every `client.py`. Downstream repositories see this diff on their next Build. Behavior is unchanged.
- **Dev dependencies:** `mypy` for the typing tests.
- **Release:** `feat:` (minor). Type checkers may now report real errors in callers' code that `Any` used to hide. That's the point, but it's worth a changelog note.
