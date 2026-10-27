## Why

`graphql_route` checks that a document is well-formed when graphql-core is installed, but it doesn't check the document against the API's schema. So a misspelled field (`viewer { logn }`), a wrong argument type, or `$owner: Int!` where the API wants `String!` passes import and only fails when the server answers with `errors`. GraphQL is fully typed, so these mistakes can be caught when the class is created, the same way `@route` catches an unused parameter. Loading a schema is also the first building block of a later `apiroute generate graphql`.

## What Changes

- New class attribute `graphql_schema` on a `Client` or `Section`. It can be a path to a schema file (`.graphql`, `.graphqls` or `.gql`) or to an introspection result (`.json`), or a `graphql.GraphQLSchema` object.
  - A relative path is resolved against the directory of the module that declares the attribute, so a client in an installed package can ship its schema next to it.
- When a schema is set, every `graphql_route` on that class, its subclasses and its nested sections is validated with graphql-core. Validation covers fields, arguments, variable types, fragments and the operation's root type.
  - Every problem is reported in one `RouteDefinitionError` that names the route and gives each problem's line and column.
  - Validation happens when the class is created, or on first use with `compile_routes = "lazy"`.
- A section without its own `graphql_schema` uses the schema of the class it's nested in. `graphql_schema = None` turns validation off for a class or section.
- New `graphql_route(..., validate=False)` skips the schema check for one operation, for fields the schema file doesn't cover yet, such as previews or schema drift.
- A set `graphql_schema` without graphql-core installed is a `RouteDefinitionError` that says `pip install apiroute[graphql]`. Unset, nothing changes and graphql-core stays optional.
- Each schema file is loaded once per process.

## Capabilities

### New Capabilities
- `graphql-schema-validation`: declaring a client's GraphQL schema, loading it, and validating `graphql_route` documents against it when routes are compiled.

### Modified Capabilities
<!-- None: openspec/specs/ is empty (add-graphql-routes is not archived yet). -->

## Impact

- **New:**
  - `src/apiroute/graphql/graphql_schema_loader.py` (reused by the future codegen)
  - `src/apiroute/graphql/graphql_schema_check.py`
- **Changed:**
  - `GraphQLRouteMethod` and `GraphQLRouteBuilder` validate when compiling.
  - `graphql_route` and `GraphQLRouteOptions` gain `validate`.
  - `RouteMethod` gains a no-op `nested_in(root)` hook.
  - `Router.__init_subclass__` calls that hook for the routes of nested sections once the enclosing class exists.
- **Dependencies:** none new. graphql-core is still the optional `graphql` extra.
- **Docs:** the README GraphQL section, and the "Checking documents" bullet that currently says documents aren't checked against a schema.
- **Compatibility:** purely additive. Without `graphql_schema`, behavior is identical. Release type: `feat:` (minor).
