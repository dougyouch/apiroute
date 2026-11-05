import httpx

from apiroute.request_spec import RequestSpec


def full_url(spec: RequestSpec) -> httpx.URL:
    """The URL a request goes to, its params merged into the query as httpx merges them."""
    return httpx.URL(spec.url).copy_merge_params(httpx.QueryParams(tuple(spec.params)))
