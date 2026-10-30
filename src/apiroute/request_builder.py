from collections.abc import Mapping
from typing import Any
from urllib.parse import parse_qsl, urlsplit, urlunsplit

from apiroute.body_encoder import BodyEncoder
from apiroute.client_config import ClientConfig
from apiroute.idempotency_key import IdempotencyKey
from apiroute.placeholder_resolver import PlaceholderResolver
from apiroute.query_encoder import QueryEncoder
from apiroute.request_options import RequestOptions
from apiroute.request_spec import RequestSpec
from apiroute.route_definition import RouteDefinition


class RequestBuilder:
    """Turns a route, the call's values and the config into a RequestSpec. No I/O.

    Later values win: class config, then the route, then its annotated arguments, then
    with_options. A None header or query value at any level leaves it out. A query string in
    base_url itself is kept and sent first. A with_options
    body is shallow-merged over the route's body when both are dicts, and replaces it otherwise.
    A with_options url replaces the base URL, path and query: only the client's own query
    parameters (an API key) are added to it, when the URL doesn't carry them already. An empty
    route path ("") sends the base URL as written, trailing slash included: a client built per
    URL (one feed, one webhook) must not have its URL changed.
    """

    def __init__(self, config: ClientConfig, root: Any, options: RequestOptions):
        self._config = config
        self._root = root
        self._options = options

    def build(self, definition: RouteDefinition, values: Mapping[str, Any]) -> RequestSpec:
        resolve = PlaceholderResolver(values, self._root)
        content, content_type = self._content(definition, values, resolve)
        return RequestSpec(
            method=definition.http_method,
            url=self._url(definition, resolve),
            headers=self._headers(definition, values, content_type),
            params=self._params(definition, values, resolve),
            content=content,
            timeout=self._timeout(definition),
            operation=definition.operation or definition.name,
            follow_redirects=self._config.follow_redirects,
        )

    def _url(self, definition: RouteDefinition, resolve: PlaceholderResolver) -> str:
        if self._options.url is not None:
            return urlunsplit(urlsplit(self._options.url)._replace(query="", fragment=""))
        if self._config.base_url is None:
            raise ValueError(f"{definition.name}: no base_url is configured")
        path = definition.path.render(resolve, self._root.escape_path)
        base = urlunsplit(urlsplit(self._config.base_url)._replace(query="", fragment=""))
        return base.rstrip("/") + path if path else base

    def _headers(
        self, definition: RouteDefinition, values: Mapping[str, Any], content_type: str | None
    ) -> dict[str, str]:
        headers: dict[str, tuple[str, Any]] = {}
        _merge_headers(headers, self._dynamic(self._config.headers))
        if definition.headers is not None:
            _merge_headers(
                headers, definition.headers.render(PlaceholderResolver(values, self._root))
            )
        if content_type and "content-type" not in headers:
            headers["content-type"] = ("Content-Type", content_type)
        _merge_headers(headers, self._bound(definition, values, "header"))
        _merge_headers(headers, self._options.headers or {})
        key = IdempotencyKey(definition, self._config)
        if key.header_name is not None and key.header_name.lower() not in headers:
            headers[key.header_name.lower()] = (key.header_name, key.new_value())
        return {name: str(value) for name, value in headers.values() if value is not None}

    def _params(
        self,
        definition: RouteDefinition,
        values: Mapping[str, Any],
        resolve: PlaceholderResolver,
    ) -> list[tuple[str, str]]:
        if self._options.url is not None:
            return self._url_params(self._options.url)
        query = dict(self._dynamic(self._config.query_params))
        if definition.query is not None:
            query.update(definition.query.render(resolve))
        query.update(self._bound(definition, values, "query"))
        query.update(self._options.query or {})
        encoded = self._encode_query(
            {name: value for name, value in query.items() if value is not None}
        )
        return self._base_url_params() + list(encoded)

    def _url_params(self, url: str) -> list[tuple[str, str]]:
        """A replacing URL's own query, after the client's parameters it doesn't carry."""
        own = parse_qsl(urlsplit(url).query, keep_blank_values=True)
        names = {name for name, _ in own}
        query = self._dynamic(self._config.query_params)
        client = self._base_url_params() + list(
            self._encode_query({name: value for name, value in query.items() if value is not None})
        )
        return [(name, value) for name, value in client if name not in names] + own

    def _base_url_params(self) -> list[tuple[str, str]]:
        """A base_url's own query (a provider key such as ?api-key=...), sent first. httpx replaces
        a URL's query with `params`, so it has to travel as params to reach the wire."""
        return parse_qsl(urlsplit(self._config.base_url or "").query, keep_blank_values=True)

    def _encode_query(self, query: dict[str, Any]) -> list[tuple[str, str]]:
        if callable(self._config.query_format):
            return self._config.query_format(self._root, query)
        return QueryEncoder(self._config.query_format).encode(query)

    def _content(
        self,
        definition: RouteDefinition,
        values: Mapping[str, Any],
        resolve: PlaceholderResolver,
    ) -> tuple[bytes | str | None, str | None]:
        data = self._route_body(definition, values, resolve)
        if self._options.body is not None:
            data = _merge_body(data, self._options.body)
        body_format = definition.body_format or self._config.body_format
        # a format may need a body even when there's no data: a SOAP envelope always is one
        if data is None and not getattr(body_format, "encodes_empty", False):
            return None, None
        return BodyEncoder(body_format).encode(self._root, data)

    def _route_body(
        self,
        definition: RouteDefinition,
        values: Mapping[str, Any],
        resolve: PlaceholderResolver,
    ) -> Any:
        if definition.literal_body is not None:
            return definition.literal_body
        if definition.body is not None:
            return definition.body.render(resolve)
        if definition.body_param is not None:
            return values.get(definition.body_param)
        return None

    def _timeout(self, definition: RouteDefinition) -> float | None:
        if self._options.timeout is not None:
            return self._options.timeout
        if definition.timeout is not None:
            return definition.timeout
        return self._config.timeout

    def _dynamic(self, mapping: Mapping[str, Any]) -> dict[str, Any]:
        """Callable values are called with the root client on every request."""
        return {
            name: value(self._root) if callable(value) else value for name, value in mapping.items()
        }

    def _bound(self, definition: RouteDefinition, values: Mapping[str, Any], location: str):
        return {
            binding.key: values[binding.param]
            for binding in definition.bindings
            if binding.location == location and values.get(binding.param) is not None
        }


def _merge_body(body: Any, override: Any) -> Any:
    """A dict override is merged over a dict body, as the gem did before 2021-08, and a None
    value removes that key; anything else replaces the body."""
    if not isinstance(body, Mapping) or not isinstance(override, Mapping):
        return override
    merged = {**body, **override}
    return {
        name: value
        for name, value in merged.items()
        if not (name in override and override[name] is None)
    }


def _merge_headers(headers: dict[str, tuple[str, Any]], source: Mapping[str, Any]) -> None:
    """Header names are case-insensitive, so a later X-Id replaces an earlier x-id."""
    for name, value in source.items():
        headers[name.lower()] = (name, value)
