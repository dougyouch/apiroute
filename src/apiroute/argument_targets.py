class ArgumentTarget:
    """Marks a route parameter that no {placeholder} names, saying where its value goes.

    Use the class (`state: Query`) or an instance with a name (`sort: Query("sort_by")`),
    or inside Annotated (`state: Annotated[str | None, Query()] = None`).
    """

    location = ""

    def __init__(self, name: str | None = None):
        self.name = name

    def key_for(self, param_name: str) -> str:
        return self.name or param_name

    def __repr__(self) -> str:
        return f"{type(self).__name__}({self.name!r})"


class Query(ArgumentTarget):
    location = "query"


class Header(ArgumentTarget):
    location = "header"

    def key_for(self, param_name: str) -> str:
        """trace_id becomes Trace-Id unless a header name was given."""
        return self.name or "-".join(part.capitalize() for part in param_name.split("_"))


class Body(ArgumentTarget):
    location = "body"
