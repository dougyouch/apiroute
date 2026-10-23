class Result:
    """Annotates the keyword-only parameter that receives a route's processed response.

    With one, the method body runs after the request; a value it returns replaces the result:

        @route("/users/{username}")
        def get_login(self, username: str, *, data: Result) -> str:
            return data["login"]
    """
