## Context

`graphql_route` builds its `RouteSpec` when the route is compiled, in `GraphQLRouteMethod._spec_for(owner, name)`, and the class and method name are known by then. graphql-core is already an optional extra, and `check_syntax` imports it lazily. graphql-core supplies the two pieces this change needs:
- `build_schema(sdl)` / `build_client_schema(introspection)` to build a schema;
- `validate(schema, parse(document))` to check a document, returning every problem with its source locations.

The complication is **sections**. A nested `Section` class body runs, and its `__init_subclass__` compiles its routes, *before* the enclosing client class exists. A section's routes therefore can't see the client's `graphql_schema` when they compile. At run time a section reaches its root through `_parent`, but that's per instance and too late to fail at import.

## Goals / Non-Goals

**Goals:**
- One class attribute turns on full validation for every GraphQL route of a client, including routes in sections.
- All of a document's problems are reported at once, with line and column.
- Schemas are loaded once, and the loader can be reused by the codegen change.
- No cost and no import of graphql-core when `graphql_schema` is unset.

**Non-Goals:**
- Fetching a schema by introspection over HTTP when the class is created. Network access at import time is a bad default, and getting the schema file is the codegen CLI's job.
- Checking Python argument annotations against GraphQL variable types (e.g. `first: str` for `$first: Int`). That's possible later, but annotations are optional and often absent.
- Revalidating inherited routes when a subclass changes `graphql_schema`. Routes are compiled once, on the class that defines them.

## Decisions

### 1. A plain class attribute, not a `ClientConfig` setting

`graphql_schema` is read with `getattr` on the route's class, so subclasses inherit it through the MRO as any class attribute does. It isn't added to `CONFIG_ATTRIBUTES`, because `ClientConfig` holds per-request settings and is resolved at run time, while the schema matters only when compiling. *Alternative:* a `ClientConfig` field with `INHERITABLE` semantics. Rejected because config inheritance into sections is decided per request, too late to fail at import.

### 2. Sections inherit through a `nested_in` hook, called when the enclosing class is created

`RouteMethod` gains `nested_in(root: type) -> None`, a no-op by default. After `SectionAccessor.install(cls)`, `Router.__init_subclass__` walks the nested section classes recursively and calls `nested_in(cls)` on each of their `RouteMethod`s. Nested sections hear from their enclosing section first and then from the client, so the innermost enclosing class comes first.

`GraphQLRouteMethod` records each class it's nested in. To find the schema it looks at:
1. its own class, if that class has the attribute anywhere in its MRO (so `None` set there means "off");
2. otherwise each enclosing class in order, taking the first that has the attribute.

On an eagerly compiled route, `nested_in` validates right away once a schema is found. On a lazy class, it only records, and validation runs on first use as part of compiling.

*Alternative:* defer section validation to the first call. Rejected because the point is to fail at import. *Alternative:* make sections look up their parent class by `__qualname__`. Rejected because it's fragile with dynamically created classes.

The hook is generic. It says nothing about GraphQL and is invisible to `@route`, so the core stays protocol-neutral.

### 3. Loading: `.json` is introspection, anything else is SDL; paths are relative to the declaring module

`GraphQLSchemaLoader.load(source, declaring_class)` works as follows:
- A `graphql.GraphQLSchema` instance is used as is.
- A `str` or `os.PathLike` is a path. A relative path is resolved against `Path(sys.modules[c.__module__].__file__).parent`, where `c` is the first class in the MRO whose own `vars()` holds `graphql_schema`. A module without a `__file__` (a REPL, `-c`) falls back to the current directory.
- A `.json` file is introspection: the `{"data": {"__schema": ...}}` envelope or a bare `{"__schema": ...}`, read with `build_client_schema`. Any other suffix is SDL, read with `build_schema`.
- Results are cached with `functools.lru_cache` on the resolved absolute path, so ten clients pointing at one 5 MB GitHub schema parse it once.
- A missing file, invalid SDL or bad JSON raises `ValueError` naming the path. The route compiler turns that into `RouteDefinitionError`.

*Alternative:* accept an inline SDL string. Rejected because a string that might be a path or might be SDL is ambiguous. Users with inline SDL pass `graphql.build_schema(sdl)` instead, which is explicit.

### 4. Validation reports every error, with locations

`check_against_schema(document, schema)` parses the document, runs `graphql.validate`, and raises a single `ValueError` listing every problem:
```
the document doesn't match the schema:
  - Cannot query field 'logn' on type 'User'. Did you mean 'login'? (line 3, column 19)
  - Unknown argument 'frist' on field 'Repository.issues'. (line 4, column 12)
```
Wrapped by `GraphQLRouteMethod`, this becomes `RouteDefinitionError("GitHub.repo: the document doesn't match ...")`. The whole document is validated, including operations not chosen by `operation_name`, because a document with a broken sibling operation is broken. `check_syntax` still runs first, when the operation is read, so a syntax error is reported the same way with or without a schema.

### 5. Missing graphql-core with a schema set is an error, not a silent skip

Setting `graphql_schema` is an explicit request for validation. Ignoring it silently when the extra is missing would hide exactly the bugs it was set to catch. So it raises `RouteDefinitionError: graphql_schema needs graphql-core: pip install apiroute[graphql]`.

### 6. Per-route opt-out: `validate=False`

Schema files lag behind production APIs, and previews add fields that aren't in the public schema. `graphql_route(..., validate=False)` skips the schema check for one route but keeps the syntax check. *Alternative:* only a class-wide off switch. Rejected because one preview field would then disable checking for the whole client.

## Risks / Trade-offs

- **[Large schemas slow imports]** (GitHub's schema is ~5 MB of SDL, around 1 s to build) → It's loaded once per process and only when set. Lazy clients pay it on first GraphQL call instead. This is documented.
- **[The schema file drifts from the live API]** → `validate=False` per route, `graphql_schema = None` per class, and the codegen change will refresh the schema file.
- **[`nested_in` runs for every route of every section, for every client class]** → It's a no-op attribute call for `@route` methods, and sections are few.
- **[A subclass that changes `graphql_schema` doesn't revalidate inherited routes]** → This is documented, and it matches how inherited routes are compiled today (once, on the defining class).
- **[A relative path resolved against a module directory surprises users who expect the current directory]** → The error message for a missing file shows the absolute path that was tried.

## Open Questions

- Should a later change add `apiroute graphql fetch-schema <url> -o schema.graphql` to download the schema by introspection? It probably belongs with the codegen CLI.
