from apiroute.api_route_error import ApiRouteError


class RouteDefinitionError(ApiRouteError):
    """A route can't be built from its decorator and signature; raised when the class is created."""
