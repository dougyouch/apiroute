from typing import Any

import httpx


class SchemaFetcher:
    """Fetches a schema's introspection result from a GraphQL endpoint."""

    def __init__(self, client: httpx.Client | None = None):
        self._client = client

    def introspect(self, url: str, headers: dict[str, str]) -> dict[str, Any]:
        """The introspection result's data; ValueError when the endpoint refuses."""
        from graphql import get_introspection_query

        query = {"query": get_introspection_query(descriptions=True)}
        response = self._post(url, query, headers)
        if not response.is_success:
            raise ValueError(f"introspecting {url} answered HTTP {response.status_code}")
        try:
            body = response.json()
        except ValueError as error:
            raise ValueError(f"introspecting {url} didn't answer with JSON") from error
        if body.get("errors"):
            messages = "; ".join(str(e.get("message", e)) for e in body["errors"])
            raise ValueError(f"introspecting {url} failed: {messages}")
        if not isinstance(body.get("data"), dict):
            raise ValueError(f"introspecting {url} answered without data")
        return body["data"]

    def _post(self, url: str, query: dict[str, Any], headers: dict[str, str]) -> httpx.Response:
        if self._client is not None:
            return self._client.post(url, json=query, headers=headers)
        return httpx.post(url, json=query, headers=headers, timeout=60, follow_redirects=True)
