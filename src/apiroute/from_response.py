from typing import Any


class _FromResponse:
    """The default of a route's response-hook parameter: apiroute fills it with the processed
    response, so callers never pass it."""

    def __repr__(self) -> str:
        return "FROM_RESPONSE"


# Marks a response-hook parameter by its default, so its annotation can be the response's own
# type for type checkers (Result marks it by annotation):
#     def get_login(self, username: str, *, data: dict = FROM_RESPONSE) -> str:
FROM_RESPONSE: Any = _FromResponse()
