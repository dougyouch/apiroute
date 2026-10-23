# apiroute

Build API clients declaratively: one `@route` per endpoint, safe defaults, [httpx](https://www.python-httpx.org/) underneath. A Python port of the Ruby gem [client-api-builder](https://github.com/dougyouch/client-api-builder).

> Status: v0.1 in development. Sync only; async, streaming and typed returns are planned.

## Quick start

```python
from apiroute import Client, Query, Retries, Section, route


class GitHubApi(Client):
    base_url = "https://api.github.com"
    headers = {
        "Accept": "application/vnd.github.v3+json",
        "Authorization": lambda self: f"Bearer {self.access_token}",
    }
    retries = Retries.exponential(attempts=5, initial=0.1, max=10, jitter=True)

    def __init__(self, access_token: str, org: str, **kwargs):
        super().__init__(**kwargs)  # base_url=..., transport=...
        self.access_token = access_token
        self.org = org

    @route("/users/{username}")  # GET, inferred from the name
    def get_user(self, username: str) -> dict: ...

    @route("/users/{username}/repos", query={"per_page": "{per_page}"})
    def get_repos(self, username: str, per_page: int = 30) -> list: ...

    # POST, inferred; {org} comes from self.org
    @route("/orgs/{org}/repos", body={"name": "{name}", "private": "{private}"})
    def create_org_repo(self, name: str, private: bool = False) -> dict: ...

    @route("POST", "/uploads")
    def create_upload(self, body: dict) -> dict: ...

    class issues(Section):
        inherit = ("headers",)

        @route("/repos/{owner}/{repo}/issues")
        def list(self, owner: str, repo: str, state: Query = None) -> list: ...


gh = GitHubApi(access_token="ghp_...", org="acme")
gh.get_user("octocat")
gh.issues.list("acme", "api", state="open")
gh.with_options(timeout=5, retries=1).get_repos("octocat")
```

## Routes

`@route([method,] path, query=..., body=..., expected=..., returns=..., timeout=...)`

- **Method inference.** A name that is, or starts with, `post`, `create`, `add` or `insert` followed by `_` is POST. `put`, `update`, `modify` and `change` are PUT, `patch` is PATCH, and `delete`, `remove` and `destroy` are DELETE. Anything else is GET.
- **Placeholders.** Write `{name}` in paths, query values and body values (paths also take `:name`). The value comes from the argument with that name, or else from the client's attribute or method. A string that is exactly `"{name}"` keeps the value's type.
- **Other arguments** must be annotated with `Query`, `Query("name")`, `Header("X-Name")` or `Body`. The exception is a parameter named `body` on a route without a body template. Otherwise the class fails to build with `RouteDefinitionError`.
- **Returns.** Parsed JSON by default (`None` for an empty body), or `returns="text" | "bytes" | "response"`.
- **Errors.** Any status outside `expected` (any 2xx when it's unset) raises `UnexpectedResponse`, which carries the `.response`.
- **Falling back to the client.** A parameter whose default is `FROM_CLIENT` takes the client's attribute of the same name when the caller leaves it out: `def list_members(self, org: str = FROM_CLIENT)`.

### Routes without a `def`

For simple endpoints, assign the route and let the class generate the method, as the Ruby gem does:

```python
class GitHubApi(Client):
    org: str  # declared, so {org} falls back to self.org

    get_user = route("/users/:username")                             # (*, username)
    list_repos = route("/orgs/{org}/repos", query={"page": "{page}"})  # (*, org=FROM_CLIENT, page)
    create_gist = route("/gists")                                    # (*, body=None), POST


gh.get_user(username="octocat")
gh.list_repos(page=2)
```

- Every placeholder becomes a keyword-only parameter, in path, then query, then body order.
- A name the class declares (a class attribute, method, property or annotation such as `org: str`) is optional and falls back to the client. In a section, declare it on the section; the value still comes from the root client.
- POST, PUT and PATCH routes without a body template take an optional `body`.
- `help()`, `inspect.signature` and wrong-argument `TypeError`s work. Editors and type checkers can't see a signature made at runtime, though, so prefer a `def` where autocomplete and type checking matter.

### Per-request options

`client.with_options(headers=..., query=..., body=..., timeout=..., retries=..., returns=...)` returns a view of the client whose route calls also send these options. Calls can be chained.

- `headers` and `query` merge over the class and route values. A `None` value leaves that header or param out.
- `body` is shallow-merged over the route's body when both are dicts, and a `None` value removes that key. Any other body (a list or a string, or when the route has no dict body) replaces the route's body.

```python
@route("/users", body={"user": {"name": "{name}"}, "notify": True})
def create_user(self, name: str) -> dict: ...


client.with_options(body={"notify": None, "source": "import"}).create_user("Ann")
# sends {"user": {"name": "Ann"}, "source": "import"}
```

## Class settings

| Attribute | Default |
| --- | --- |
| `base_url` | none; http or https only |
| `headers`, `query_params` | `{}`. Values may be callables taking the client. Both merge down subclasses, and `None` removes a key |
| `timeout` | `30` seconds |
| `retries` | `Retries()` (one attempt) |
| `body_format` | `"json"`, `"form"` or `callable(client, data)` |
| `query_format` | `"flat"`, `"nested"` (`a[b]=1`) or `callable(client, data)` returning pairs |

Override `should_retry(self, error, attempt)` to change what is retried. By default that's httpx timeouts, network errors and protocol errors. Override `escape_path(self, value)` to change how path values are escaped.

## Transports: how requests are sent

An API class only describes the API. How its requests reach the network is a **transport**, chosen for the environment at startup rather than baked into the class. The same `GitHubApi` can open a fresh connection per request in a web server and keep a pool per thread in a background worker.

| Transport | Connections | Suits |
| --- | --- | --- |
| `OneShotTransport` (default) | a new one per request, closed once the response is read | web servers, forking process managers, low request volume |
| `PooledTransport` | one `httpx.Client` (one pool) shared by all threads | many threads or short-lived threads, HTTP/2 |
| `ThreadLocalTransport` | one `httpx.Client` per thread, closed when the thread ends | a fixed set of worker threads |
| `HttpxClientTransport` | an `httpx.Client` you own | tests (with `httpx.MockTransport`), custom setups |

Each takes `httpx.Client` keyword arguments, such as `limits`, `http2=True`, `proxy` and `verify`. The SSL context is built once per transport, so a one-shot request costs a new connection but not a reload of the CA bundle. Pooled and thread-local transports open new clients in a forked child.

```python
import httpx
from apiroute import (
    HttpxClientTransport,
    PooledTransport,
    ThreadLocalTransport,
    close_transports,
    use_transport,
)

# worker.py: each worker thread keeps its own connections
use_transport(ThreadLocalTransport())

# or one shared pool for one API, with HTTP/2
use_transport(PooledTransport(http2=True, limits=httpx.Limits(max_connections=20)), GitHubApi)

# one instance, e.g. in a test
gh = GitHubApi("token", "acme", transport=HttpxClientTransport(httpx.Client(transport=mock)))

close_transports()  # at shutdown
```

A client uses its own `transport=` argument if it was given one. Otherwise it uses the transport registered for its class or the nearest base class, and otherwise the process default. Sections use their root client's transport. A custom transport is any object with `send(spec) -> httpx.Response` and `close()`.

## Development

```bash
uv sync
uv run pytest
uv run ruff check .
```
