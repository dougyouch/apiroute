# graphql-schema-validation Specification

## Purpose
TBD - created by archiving change add-graphql-schema-validation. Update Purpose after archive.
## Requirements
### Requirement: A client declares its GraphQL schema
A `Client` or `Section` SHALL accept a `graphql_schema` class attribute. It is a path (`str` or `os.PathLike`) to an SDL file or a `.json` introspection result, or a `graphql.GraphQLSchema`. Subclasses SHALL inherit it like any class attribute. A relative path SHALL be resolved against the directory of the module that defines the class declaring the attribute.

#### Scenario: SDL file next to the client module
- **WHEN** a client in `pkg/client.py` sets `graphql_schema = "schema.graphql"` and `pkg/schema.graphql` exists
- **THEN** its GraphQL routes are validated against that schema, whatever the current directory is

#### Scenario: Introspection JSON
- **WHEN** `graphql_schema` names a `.json` file holding `{"data": {"__schema": ...}}` or `{"__schema": ...}`
- **THEN** the schema is built from that introspection result

#### Scenario: A schema object
- **WHEN** `graphql_schema = graphql.build_schema(sdl)`
- **THEN** that schema is used as is

#### Scenario: Subclasses inherit the schema
- **WHEN** a client subclass declares GraphQL routes and its base class sets `graphql_schema`
- **THEN** the subclass's routes are validated against the base class's schema

### Requirement: Routes are validated against the schema when compiled
When a route's class (or an enclosing class, for sections) has a `graphql_schema`, every `graphql_route` document SHALL be validated against it with graphql-core when the route is compiled: when the class is created, or on first use with `compile_routes = "lazy"`. A document with problems SHALL raise one `RouteDefinitionError`. It names the route and lists every problem with its line and column.

#### Scenario: Unknown field
- **WHEN** a client with a schema declares `graphql_route("query V { viewer { logn } }")` and `User` has no `logn` field
- **THEN** creating the class raises `RouteDefinitionError` whose message names the route and includes "Cannot query field 'logn' on type 'User'" and its line and column

#### Scenario: Wrong variable type
- **WHEN** a document declares `$owner: Int!` and passes it to an argument of type `String!`
- **THEN** creating the class raises `RouteDefinitionError` describing the type mismatch

#### Scenario: Every problem is reported
- **WHEN** a document has an unknown field and a missing required argument
- **THEN** one `RouteDefinitionError` lists both

#### Scenario: Valid documents pass
- **WHEN** every document matches the schema
- **THEN** the class is created and its routes work as before

#### Scenario: Lazy classes validate on first use
- **WHEN** a client with `compile_routes = "lazy"` and a schema has an invalid document
- **THEN** creating the class succeeds, and the first call to that route raises `RouteDefinitionError`

### Requirement: Sections use the schema of the class they're nested in
A section without its own `graphql_schema` SHALL validate its GraphQL routes against the schema of the nearest enclosing class that has one. This SHALL happen when that enclosing class is created, or on first use for lazy sections. A section's own `graphql_schema`, including `None`, SHALL take precedence.

#### Scenario: Section inside a client with a schema
- **WHEN** a client with a schema nests `class admin(Section)` whose GraphQL route queries an unknown field
- **THEN** creating the client class raises `RouteDefinitionError` naming `Client.admin.<route>`

#### Scenario: Nested sections
- **WHEN** a section nested two levels deep has an invalid document and only the client sets a schema
- **THEN** creating the client class raises `RouteDefinitionError`

#### Scenario: Section opts out
- **WHEN** a section sets `graphql_schema = None`
- **THEN** its routes are not validated against the client's schema

### Requirement: Validation can be skipped per route
`graphql_route(..., validate=False)` SHALL skip the schema check for that route. The syntax check still runs when graphql-core is installed.

#### Scenario: Preview field
- **WHEN** a route queries a field missing from the schema file and passes `validate=False`
- **THEN** the class is created and the route works

### Requirement: Schema problems are reported clearly
A `graphql_schema` that can't be loaded (a missing file, invalid SDL, malformed JSON) SHALL raise `RouteDefinitionError` naming the route and the absolute path tried. A `graphql_schema` set while graphql-core isn't installed SHALL raise `RouteDefinitionError` telling the user to `pip install apiroute[graphql]`. A class without `graphql_schema` SHALL NOT import graphql-core for validation.

#### Scenario: Missing file
- **WHEN** `graphql_schema = "missing.graphql"` and no such file exists next to the module
- **THEN** creating the class raises `RouteDefinitionError` that includes the absolute path

#### Scenario: graphql-core not installed
- **WHEN** graphql-core can't be imported and a client sets `graphql_schema`
- **THEN** creating the class raises `RouteDefinitionError` mentioning `apiroute[graphql]`

### Requirement: Schemas are loaded once
A schema file SHALL be read and built at most once per process for a given absolute path, however many classes or routes use it.

#### Scenario: Shared schema
- **WHEN** two client classes set `graphql_schema` to the same file
- **THEN** the file is parsed once

