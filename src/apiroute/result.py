class Result:
    """Annotates the keyword-only parameter that receives a route's processed response.

    With one, the method body runs after the request; a value it returns replaces the result:

        @route("/users/{username}")
        def get_login(self, username: str, *, data: Result) -> str:
            return data["login"]

    For type checkers, mark it with FROM_RESPONSE as its default instead, so its annotation
    can be the response's type and callers aren't asked for it:
    `*, data: dict = FROM_RESPONSE`.
    """
