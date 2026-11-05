from apiroute.api_route_error import ApiRouteError


class WebhookSignatureError(ApiRouteError):
    """A webhook request's signature is missing, malformed, wrong, or too old to trust. Answer
    such a request with 400 or 401 and don't act on its body."""
