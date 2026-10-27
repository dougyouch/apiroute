## ADDED Requirements

### Requirement: A client can decide idempotency per request
`Client.idempotent(self, request)` SHALL be called with each call's built `RequestSpec` before its first attempt. A `True` or `False` answer SHALL decide whether errors that may follow sending are retried, overriding the route's own idempotency (its method default or `idempotent=`). `None`, the default, SHALL keep the route's own. A request carrying an idempotency key SHALL still be retried as idempotent. Sections SHALL use their root client's hook.

#### Scenario: Marking reads safe
- **WHEN** a client's `idempotent` returns `True` for requests whose `operation` starts with `Get`, and a `POST` route with operation `GetItem` gets `httpx.ReadTimeout`
- **THEN** it's retried, while a `POST` route with operation `AddItem` isn't

#### Scenario: Marking a GET unsafe
- **WHEN** the hook returns `False` for a `GET` route
- **THEN** that route isn't retried after `httpx.ReadTimeout`

#### Scenario: Default
- **WHEN** a client doesn't override `idempotent`
- **THEN** every route keeps its 2.0 behavior

#### Scenario: Sections
- **WHEN** a section's `POST` route is called on a client whose hook marks it idempotent
- **THEN** it's retried after `httpx.ReadTimeout`

### Requirement: Generated names don't shadow client settings and hooks
The code generator SHALL NOT give a generated method one of the names a client already uses, including `idempotent`, `idempotency_key`, `follow_redirects`, `check_response`, `redact_url` and `soap_header`; such an operation SHALL get a suffixed name.

#### Scenario: An operation named idempotent
- **WHEN** a spec has an operation whose Python name would be `idempotent`
- **THEN** the generated method is named `idempotent_2`
