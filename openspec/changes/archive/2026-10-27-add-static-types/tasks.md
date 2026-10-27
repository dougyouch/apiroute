## 1. Runtime typing

- [x] 1.1 `RouteMethod(Generic[P, R])` with overloaded `__get__` and a loosely typed `__call__`; `RouteDecorator.__call__` generic, plus a typing-only `__get__` for routes without a `def`
- [x] 1.2 `GraphQLRouteMethod` and `GraphQLRouteDecorator` generic in the same way
- [x] 1.3 `SectionType` metaclass with a typing-only `__get__`, used by `Section`
- [x] 1.4 `TypedClient.with_options()` returns the same type; `aio` is `Any`
- [x] 1.5 `FROM_CLIENT` typed `Any`; `FROM_RESPONSE` marks a hook parameter by its default (compiler, export, tests)

## 2. Codegen

- [x] 2.1 `DictClientEmitter`: `TYPE_CHECKING` imports and annotations for lazy section and `.models` attributes, a mypy `empty-body` header, and `...` ending every route body
- [x] 2.2 Tests: the emitted lines, laziness unchanged, and OpenAPI/WSDL/GraphQL fixtures otherwise unchanged

## 3. Typing tests

- [x] 3.1 `mypy` in the dev dependency group
- [x] 3.2 Typing checks run by pytest: sample code with `assert_type` (routes, routes without a `def`, GraphQL and paginated routes, nested sections, `TypedClient`) must pass mypy, a sample with wrong calls must fail on exactly the expected lines, and a generated package plus a caller must pass mypy
- [x] 3.3 A manual pyright run over the same samples (pyright needs Node, so it isn't in CI)

## 4. Docs and checks

- [x] 4.1 README: a "Type checking" section (what's typed, mypy versus pyright for nested sections, routes without a `def`, the `Result` default, `.aio` being `Any`)
- [x] 4.2 Ruff, the full suite (with the exit code checked), the lowest-dependencies run, and `openspec validate --all --strict`
