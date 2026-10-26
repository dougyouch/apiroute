# apiroute

Build API clients declaratively: one `@route` per endpoint, safe defaults, [httpx](https://www.python-httpx.org/) underneath. A Python port of the Ruby gem [client-api-builder](https://github.com/dougyouch/client-api-builder).

## Installation

```bash
pip install apiroute            # or: uv add apiroute
pip install apiroute[pydantic]  # to return pydantic models
pip install apiroute[codegen]   # to generate clients from OpenAPI/Swagger specs and WSDLs
pip install apiroute[soap]      # to run generated SOAP clients
```

apiroute needs Python 3.10 or newer, and httpx.

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

`@route([method,] path, query=..., body=..., expected=..., returns=..., timeout=..., stream=...)`

- **Method inference.** A name that is, or starts with, `post`, `create`, `add` or `insert` followed by `_` is POST. `put`, `update`, `modify` and `change` are PUT, `patch` is PATCH, and `delete`, `remove` and `destroy` are DELETE. Anything else is GET.
- **Placeholders.** Write `{name}` in paths, query values and body values (paths also take `:name`). The value comes from the argument with that name, or else from the client's attribute or method. A string that is exactly `"{name}"` keeps the value's type.
- **Other arguments** must be annotated with `Query`, `Query("name")`, `Header("X-Name")` or `Body`. The exception is a parameter named `body` on a route without a body template. Otherwise the class fails to build with `RouteDefinitionError`.
- **Returns.** Parsed JSON by default (`None` for an empty body), or `returns="text" | "bytes" | "response"`.
- **Errors.** Any status outside `expected` (any 2xx when it's unset) raises `UnexpectedResponse`, which carries the `.response`.
- **Falling back to the client.** A parameter whose default is `FROM_CLIENT` takes the client's attribute of the same name when the caller leaves it out: `def list_members(self, org: str = FROM_CLIENT)`.

### Response hook

Give the method a keyword-only parameter annotated `Result` and its body runs after the request. The parameter receives the processed result (parsed JSON, or whatever `returns` asks for), and a value the body returns replaces it. Returning `None` keeps the result. Callers never see the parameter.

```python
@route("/users/{username}")
def get_login(self, username: str, *, data: Result) -> str:
    return data["login"]


gh.get_login("octocat")  # "octocat"
```

### Streaming

| `stream=` | Destination | Returns |
| --- | --- | --- |
| `"file"` | the path in a `file` parameter, written `wb` | the `httpx.Response` |
| `"io"` | the writable object in an `io` parameter, left open | the `httpx.Response` |
| `"iter"` | none | a `ChunkIterator` of `bytes` (an `AsyncChunkIterator` through `.aio`) |

```python
@route("/files/{id}", stream="file")
def download(self, id: int, file: str): ...


with gh.get_events() as events:  # stream="iter"; the with block closes the connection
    for chunk in events:
        ...
```

- The status is checked before any of the body is read. An error response raises `UnexpectedResponse` with its body readable, and nothing is written: an existing file is left untouched.
- File paths with a null byte or a `..` segment are rejected before the request is sent, as in the Ruby gem. Absolute paths are allowed.
- Opening the stream is retried like any request; a failure while the body is being read is raised, not retried.
- In async calls, an `io` object whose `write` returns an awaitable (such as an aiofiles file) is awaited.

### Typed returns

A return annotation that contains a dataclass or a pydantic model converts the JSON response. That includes `-> User`, `-> list[User]`, `-> dict[str, User]` and `-> User | None`. Routes without a `def` take `model=` instead. Plain annotations (`dict`, `list`, `Any`) leave the JSON as parsed.

```python
@route("/users/{username}")
def get_user(self, username: str) -> User: ...


list_users = route("/users", model=list[User])
```

- **Pydantic models** are validated with pydantic's `TypeAdapter`, with its usual type coercion. Install it with `pip install apiroute[pydantic]`.
- **Dataclasses** are built by apiroute itself, so they don't need pydantic. Keys the dataclass doesn't declare are ignored, and a missing required field fails.
- **Errors.** A body that doesn't fit raises `ResponseValidationError`, which carries the `.response` and the underlying `.error`.
- **With a response hook,** the `Result` parameter's type is used (`user: Annotated[User, Result()]`). The return annotation then describes what the hook returns.
- **Late-defined types.** A model defined below the client class (`-> "Team"`) is looked up on the first call.
- **Other return modes.** Only JSON is converted; `returns="text"`, `"bytes"`, `"response"` and streams are left alone.

### Routes without a `def`

For simple endpoints, assign the route and let the class generate the method, as the Ruby gem does:

```python
class GitHubApi(Client):
    org: str  # declared, so {org} falls back to self.org

    get_user = route("/users/:username")  # (*, username)
    list_repos = route("/orgs/{org}/repos", query={"page": "{page}"})  # (*, org=FROM_CLIENT, page)
    create_gist = route("/gists")  # (*, body=None), POST


gh.get_user(username="octocat")
gh.list_repos(page=2)
```

- Every placeholder becomes a keyword-only parameter, in path, then query, then body order.
- A name the class declares (a class attribute, method, property or annotation such as `org: str`) is optional and falls back to the client. In a section, declare it on the section; the value still comes from the root client.
- POST, PUT and PATCH routes without a body template take an optional `body`.
- `help()`, `inspect.signature` and wrong-argument `TypeError`s work. Editors and type checkers can't see a signature made at runtime, though, so prefer a `def` where autocomplete and type checking matter.

### Namespaces

Routes declared inside a `namespace` block get its path prefix, as in the gem. Blocks nest.

```python
class Api(Client):
    with namespace("/admin"):
        list_users = route("/users")  # GET /admin/users

        @route("/users/{id}")
        def delete_user(self, id: int): ...  # DELETE /admin/users/{id}
```

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

## Sections

A nested class that subclasses `Section` groups routes under the client, as `client.<class name>`:

```python
class Api(Client):
    base_url = "https://api.example.com"
    headers = {"Authorization": lambda self: f"Bearer {self.token}"}

    class users(Section):
        inherit = ("headers",)  # use the client's headers too

        list = route("/users")

    class uploads(Section):
        base_url = "https://uploads.example.com"  # its own host
        headers = {"Authorization": lambda self: f"Upload {self.upload_token}"}

        create = route("/files")


api.users.list()
api.uploads.create(body=data)
```

- A section uses its parent's `base_url` unless it sets one. It inherits nothing else unless listed in `inherit`, as in the gem: `"headers"` and `"query_params"` merge under the section's own, and `"retries"` and `"timeout"` are the root client's unless the section sets its own. Generated sections inherit all four, so a client's retry and timeout policy, from `--base-class` or a subclass, covers every route.
- `{name}` placeholders, callable headers, the overridable methods and the transport all belong to the root client, so a section can use the client's state.
- Sections nest, are created once per client, and remain reachable as classes (`Api.users`).

## Retries

```python
retries = Retries(attempts=3, sleep=0.5)  # 3 attempts in total, 0.5 s apart
retries = Retries.exponential(attempts=5, initial=0.1, max=10)  # 0.1, 0.2, 0.4, 0.8 s
retries = Retries(attempts=5, sleep=0.1, backoff=2, max_sleep=10, jitter=True)
```

- `attempts` is the total number of attempts. The default is one, so nothing is retried until you configure it.
- The sleep before retry n is `sleep * backoff ** (n - 1)`, capped at `max_sleep`. `jitter=True` sleeps a random time up to that; a number from 0 to 1 shortens it by up to that fraction.
- Only timeouts, network errors and protocol errors are retried, unless `should_retry` says otherwise. A retried `UnexpectedResponse` with a `Retry-After` header waits that long, capped at `max_sleep`.
- `with_options(retries=3)` changes the attempts for one call; `with_options(retries=Retries(...))` replaces the policy.

## Errors

| Exception | Raised when | Carries |
| --- | --- | --- |
| `RouteDefinitionError` | a route is wrong (an unused parameter, a bad template value or option); raised when the class is created | the class, route and reason in its message |
| `UnexpectedResponse` | the status isn't expected (any 2xx when `expected` is unset), or a JSON route's body isn't JSON | `.response`, `.status_code`, `.request`, `.route_name` |
| `ResponseValidationError` | the JSON doesn't fit the route's model | `.response`, `.error`, `.route_name` |
| `httpx.TransportError` subclasses | the network fails, after retries run out | httpx's details |
| `ValueError` | a class setting is invalid (a `base_url` scheme, `body_format`, `inherit`), or a streamed file path is unsafe | the reason in its message |

The first three derive from `ApiRouteError`. `client.last_response` holds the most recent response for debugging; it is per client, so don't rely on it when one client is shared between threads.

## Class settings

| Attribute | Default |
| --- | --- |
| `base_url` | none; http or https only |
| `headers`, `query_params` | `{}`. Values may be callables taking the client. Both merge down subclasses, and `None` removes a key |
| `timeout` | `30` seconds |
| `retries` | `Retries()` (one attempt) |
| `body_format` | `"json"`, `"form"` or `callable(client, data)` |
| `query_format` | `"flat"`, `"nested"` (`a[b]=1`) or `callable(client, data)` returning pairs |
| `follow_redirects` | `None`: the transport's httpx setting (httpx doesn't follow). `True` follows 3xx answers for this API whatever the transport; a section uses its parent's unless it sets one |

### Methods to override

| Method | Runs | Default |
| --- | --- | --- |
| `on_request(self, request)` | before every attempt, sync or async; may return a changed `RequestSpec` | sends the request as is |
| `on_response(self, request, response, elapsed)` | after every response, whatever its status; for streams, before the body is read | nothing |
| `check_response(self, request, response)` | after `on_response`, inside the retry loop and before the status check; raise to reject the response | accepts it |
| `should_retry(self, error, attempt)` | when an attempt fails | retries httpx timeouts, network and protocol errors |
| `escape_path(self, value)` | for every path value | percent-encodes everything but `A-Z a-z 0-9 - . _ ~` |
| `redact_url(self, url)` | for the URL in an `UnexpectedResponse` message, and so in retry log lines | masks secret-looking query values and a userinfo password |
| `soap_header(self, operation)` | when building a SOAP envelope; returns a dict for its Header | no Header |

`request.operation` names the call: the route's `operation=` (generated clients set it to the spec's `operationId` or WSDL operation name), else the method name. It's useful for logging, metrics and APIs that want the call name in the request.

```python
class SignedApi(Client):
    def on_request(self, request):
        signature = hmac.new(self.secret, request.url.encode(), "sha256").hexdigest()
        return dataclasses.replace(request, headers={**request.headers, "X-Signature": signature})

    def on_response(self, request, response, elapsed):
        metrics.timing("api.request", elapsed, tags=[f"status:{response.status_code}"])
```

Network errors don't reach `on_response`; every failed attempt is logged on the `apiroute` logger, with the route, the attempt number and the error.

`check_response` is for APIs that report a failure inside a successful response, such as a 200 whose body says the call was rate limited. Whatever it raises goes through `should_retry` like any other failure:

```python
class RateLimited(Exception): ...


class TokenApi(Client):
    retries = Retries.exponential(attempts=5, initial=1, max=30)

    def check_response(self, request, response):
        if response.json().get("code") == 4029:  # "too many requests", sent with status 200
            raise RateLimited(request.operation)

    def should_retry(self, error, attempt):
        return isinstance(error, RateLimited) or super().should_retry(error, attempt)
```

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

A client uses its own `transport=` argument if it was given one. Otherwise it uses the transport registered for its class or the nearest base class, and otherwise the process default. Sections use their root client's transport. A custom transport is any object with `send(spec) -> httpx.Response`, `stream(spec)` (a context manager yielding an unread `httpx.Response`, needed only for streaming routes) and `close()`.

## Async

The same client class works with `await`: `client.aio` is a view whose route calls return coroutines.

```python
user = gh.get_user("octocat")  # sync
user = await gh.aio.get_user("octocat")  # async, same class and routes
issues = await gh.aio.issues.list("acme", "api")  # sections too
await gh.aio.with_options(timeout=5).get_user("a")  # with_options, in either order
```

Async calls have transports of their own, registered beside the sync ones. `use_transport` sends an async transport (one whose `send` is a coroutine) to the async side, so configuring one side never changes the other.

| Transport | Connections |
| --- | --- |
| `AsyncOneShotTransport` (default) | a new one per request |
| `AsyncPooledTransport` | one `httpx.AsyncClient` per event loop (an `AsyncClient` can't be shared across loops) |
| `AsyncHttpxClientTransport` | an `httpx.AsyncClient` you own |

```python
use_transport(AsyncPooledTransport(http2=True))  # async default for every client
gh = GitHubApi("token", "acme", async_transport=AsyncHttpxClientTransport(async_client))
await aclose_transports()  # at shutdown, inside the event loop
```

Retries sleep with `asyncio.sleep`. `should_retry`, `escape_path`, `on_request`, `on_response` and callable headers stay plain sync methods, shared by both sides.

## Code generation

`apiroute generate` writes a client package from an OpenAPI 3.0/3.1 or Swagger 2.0 spec, or from a WSDL 1.1 document (document/literal, SOAP 1.1 and 1.2). Specs can be file paths or URLs, in JSON or YAML.

```bash
apiroute generate openapi github.yaml -o gh --client-name GitHubApi           # dict routes only
apiroute generate openapi github.yaml -o gh --client-name GitHubApi --models  # plus pydantic models
apiroute generate wsdl "https://example.com/weather?wsdl" -o weather --models
```

The package has two layers:

```python
from gh import GitHubApi


class MyGitHub(GitHubApi):  # yours, outside gh/: regenerating never touches it
    headers = {"Authorization": lambda self: f"Bearer {self.token}"}

    def __init__(self, token: str, **kwargs):
        super().__init__(**kwargs)
        self.token = token


gh = MyGitHub("ghp_...")
gh.meta.get()  # each tag is a section; dicts in and out
gh.repos.get("octocat", "hello-world")
gh.repos.models.get("octocat", "hello-world")  # -> FullRepository (with --models)
await gh.repos.models.aio.get("octocat", "hello-world")
```

```text
gh/
  client.py              GitHubApi: untagged routes; each tag a lazily imported section
  models/                with --models
    client.py            gh.models: typed versions of the root routes
    models.py            a lazy index of the models
    schemas/*.py         one module per model (models that refer to each other share one)
  repos/
    client.py            gh.repos: the tag's dict routes
    models/
      client.py, models.py, schemas/*.py
```

Nothing is imported until it's used. On GitHub's spec (1,242 operations, 4,035 models), constructing the client takes 0.6 ms, a dict call about 3 ms all in, and the first typed call costs pydantic's own import plus a few milliseconds for the models it returns.

- **Your code goes outside the package.** Subclass the client to add behaviour, such as auth a spec doesn't declare (above); headers merge down subclasses. Regenerating removes only files the generator wrote, and refuses to write into a directory it didn't create.
- **Auth can live in a hand-written base class.** `--base-class mypackage.auth:MyAuth` makes the generated root client extend `MyAuth` (a `Client` subclass) instead of `Client`, and leaves out the spec's security schemes. The base class owns credentials, through `headers`, `query_params`, `on_request` or, for SOAP, `soap_header`, and regenerating never touches it:

  ```python
  class TradingAuth(Client):  # eBay Trading: credentials in the SOAP header, call name in the query
      def __init__(self, token: str, **kwargs):
          super().__init__(**kwargs)
          self.token = token

      def soap_header(self, operation):
          return {"RequesterCredentials": {"eBayAuthToken": self.token}}

      def on_request(self, request):
          return dataclasses.replace(
              request, params=[*request.params, ("callname", request.operation)]
          )
  ```
- **A relative server URL needs a host.** A spec read from a URL resolves a relative `servers` entry (`/api/v2`) against the spec's own address. Read from a file, it can't, so pass the host: `--base-url https://api.example.com/api/v2`. The option also overrides the spec's servers.
- **Output passes `ruff check` and `ruff format`.** When ruff is installed, the generator runs it over the output; `--no-format` skips that.
- **OpenAPI:** tags become sections, `operationId`s become method names, and path, query and header parameters become arguments. Bodies can be JSON, form or multipart; responses can be JSON, text or binary. Schemas become models, with `allOf` merged, `oneOf`/`anyOf` as unions and enums as `Literal`. Bearer, basic and API key auth become constructor arguments.
- **WSDL:** each operation becomes a POST route with its `SOAPAction`. Bodies are dicts in the xmltodict shape: child elements as keys, `"@attr"` for attributes, `"#text"` for text content, and `"{namespace}local"` for an element from another namespace. Faults raise `apiroute.soap.SoapFault`. XML is parsed with `defusedxml`.

## Security

- **Base URLs** must be `http` or `https` and have a host. This is checked when the class is created and when a `base_url` is passed to a client, which keeps a misconfiguration from reaching `file:` and similar schemes.
- **Path values** are percent-encoded so each stays one path segment: `get_file(name="a/b c")` requests `/files/a%2Fb%20c`, so a value can never add `..` or a segment. Override `escape_path` to allow `/`.
- **URLs are joined, not resolved:** the request URL is `base_url` plus the path, so a route can't replace the host.
- **Secrets stay out of messages:** an `UnexpectedResponse` shows its URL through `redact_url`, which masks the values of query parameters whose names contain a secret word (`api_key`, `apikey`, `accessToken`, `client_secret`, `sig`, ...) and a password in the userinfo. The retry log lines print that message. Override `redact_url` for a key elsewhere, such as in the path; `.request` keeps the real URL.
- **TLS** is verified by default (httpx). Turning it off takes an explicit `verify=False` on a transport.
- **Streamed files** are only opened once the status has passed, and paths with a null byte or a `..` segment are rejected.

## Thread safety

- Route definitions are compiled once, when the class is created, and never change afterwards.
- `PooledTransport` is safe to share between threads, and `ThreadLocalTransport` gives each thread its own connections. `OneShotTransport` shares nothing.
- A client instance holds no connections, so one instance can be shared between threads. The exception is `last_response`, which is per instance and changes with every request.
- `namespace` blocks are tracked per thread.

## Development

```bash
uv sync
uv run pytest
uv run ruff check .
```
