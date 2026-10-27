## Context

- **Routes:** `route(...)` returns a `RouteDecorator`. Applied to a `def`, it returns a `RouteMethod`, a descriptor whose `__get__` binds the route to the client and returns a function with the method's signature (minus `self`) as `__signature__`, but annotated `-> Any`. Left on the class as is, the router replaces it with a generated `RouteMethod` when the class is created.
- **Sections:** nested `Section` classes are replaced by `SectionAccessor` descriptors. Generated clients reach sections and `.models` through `lazy(module, class)`, which returns `Any`.
- **Typed calls:** `TypedClient` subclasses (the generated `.models` views) have real method signatures, but they're only reachable through those `Any`-typed attributes.

A prototype was checked with mypy 1.13 and pyright 1.1.390, the version Pylance ships:
- `RouteMethod(Generic[P, R])` with overloaded `__get__` gives exact signatures in both.
- A metaclass `__get__` on `Section` gives instance types in pyright only. mypy types the attribute as the class, so a route reached through it is looked up on the class.

## Goals / Non-Goals

**Goals:**
- Callers get real signatures and return types from decorated routes, generated sections and typed calls, in both mypy and pyright.
- Nothing that type-checks today starts failing because of apiroute's own typing. Wherever full typing isn't possible, the type falls back to `Any`.
- No run-time behavior change, and no extra imports at run time.

**Non-Goals:**
- Typing `.aio` and `with_options()` views on clients, beyond `Any`.
- A mypy plugin.
- Removing `Result` hook parameters from the typed signature (Decision 6).

## Decisions

### 1. `RouteMethod(Generic[P, R])` with overloaded `__get__`

```python
P = ParamSpec("P")
R = TypeVar("R")


class RouteMethod(Generic[P, R]):
    def __init__(self, func: Callable[Concatenate[Any, P], R], spec: RouteSpec): ...
    @overload
    def __get__(self, instance: None, owner: type) -> RouteMethod[P, R]: ...
    @overload
    def __get__(self, instance: object, owner: type) -> Callable[P, R]: ...
    def __call__(self, *args: Any, **kwargs: Any) -> Any: ...  # Api.get_user(client, ...)
```

`RouteDecorator.__call__(self, func: Callable[Concatenate[Any, P], R]) -> RouteMethod[P, R]`. Accessed through the class, a route is the `RouteMethod`, whose `__call__` (`Api.get_user(client, ...)`) is typed loosely. That keeps class-level calls, and mypy's view of nested sections (Decision 3), at `Any` rather than producing false errors.

### 2. Routes without a `def`: `Callable[..., Any]`

`RouteDecorator.__get__` (typing-only: the router replaces the attribute when the class is created, so it never runs on a client) returns `Callable[..., Any]`. The generated signature isn't knowable statically, so this is the honest type. It accepts any call, as `Any` did. At run time it returns itself, for the rare case of a decorator left on a class that isn't a `Router`.

### 3. Nested sections: a typing-only metaclass `__get__`

```python
class SectionType(type):
    @overload
    def __get__(cls: type[S], instance: None, owner: type) -> type[S]: ...
    @overload
    def __get__(cls: type[S], instance: object, owner: type) -> S: ...
    def __get__(cls, instance, owner):
        return cls


class Section(Router, metaclass=SectionType): ...
```

At run time, `SectionAccessor` still replaces nested sections in every `Router` subclass, so this `__get__` only runs for a `Section` class stored on a non-`Router` class. It returns the class itself, which is what attribute access did before.
- **pyright and Pylance:** `client.issues` is an `issues` instance, with typed routes.
- **mypy:** the metaclass `__get__` is ignored, and `client.issues.list` is the class-level `RouteMethod`, whose loose `__call__` gives `Any`. That's today's behavior, with no false errors.

mypy rejects the `cls: type[S]` self-type on a metaclass ("erased type of self"); `# type: ignore[misc]` covers it. This is also in the README: for full types under mypy, use generated-style `lazy` sections with an annotation.

*Alternative:* a `section()` helper (`issues: IssuesSection = section(IssuesSection)`). It's left as an option for later. It changes how sections are written, while the metaclass costs callers nothing.

### 4. Generated clients annotate their lazy attributes

`DictClientEmitter` writes:
```python
if TYPE_CHECKING:
    from .models.client import HubApiModels
    from .repos.client import ReposSection
...
    repos: ReposSection = lazy(".repos.client", "ReposSection")
    models: HubApiModels = lazy(".models.client", "HubApiModels")
```
`lazy()` returns `Any`, so the assignment checks, and the annotation types the instance attribute. With `from __future__ import annotations` (already in generated files), the annotations are never evaluated, so nothing is imported at run time, and the "only the root is imported until used" guarantee holds.

Every generated dict `client.py` starts with `# mypy: disable-error-code="empty-body"`, after the header, since its routes' bodies are `...` by design. `ModelsClientEmitter` output has real bodies and doesn't need it.

### 5. `TypedClient`

- **`with_options()`:** returns `T` for a `TypeVar` bound to the class, so the same view type comes back.
- **`aio`:** returns `Any`. Its methods return coroutines of the annotated types, which no sync annotation can say, and `Any` avoids false "no attribute" errors on generated views.

### 6. `FROM_RESPONSE`, and `FROM_CLIENT` typed `Any`

A response hook's keyword-only parameter is removed from the call signature at run time, but `ParamSpec` can't remove it statically, so type checkers would ask callers for it. A default fixes that, but it must fit the annotation, and `data: Result` types the value as the marker, so `data["login"]` fails. So:
- **`FROM_RESPONSE`** (typed `Any`) marks a hook parameter by its default instead: `*, data: dict = FROM_RESPONSE`, or `*, user: User = FROM_RESPONSE`, which also converts to `User` as a `Result` parameter's type does. Callers aren't asked for it, and the hook's body sees the real type. `RouteCompiler` treats `param.default is FROM_RESPONSE` like a `Result` marker, including the keyword-only rule. `Result` keeps working.
- **`FROM_CLIENT`**, already documented as `org: str = FROM_CLIENT`, failed mypy with "Incompatible default", because it was typed as its private class. It's now typed `Any`.

Both were found by writing the typing samples.

### 7. Generated route bodies end with `...`

pyright reports "must return value on all code paths" for a function whose body is only a docstring, but it accepts `...` as a stub body. mypy flags both forms (`empty-body`, silenced by the generated header). So every generated dict route ends with `...`, after its docstring when it has one. Found running pyright over generated packages.

## Risks / Trade-offs

- **[Type checkers start flagging real mistakes in users' code]** → That's the purpose, and it gets a changelog note. Nothing changes at run time.
- **[mypy users get `Any` for hand-written nested sections]** → It's documented, and no worse than today. Generated sections are fully typed in both checkers.
- **[Generated output changes in every client repository]** → Annotations and one comment, with no behavior change.
- **[A user's `Section` subclass with its own metaclass]** → It must derive from `SectionType`. This is rare and documented.

## Open Questions

- Should a later change offer typed `.aio` views, for example generated `...AsyncModels` classes?
