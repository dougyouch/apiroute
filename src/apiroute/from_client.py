class _FromClient:
    """The default of a route parameter that, when left out, comes from the client instead."""

    def __repr__(self) -> str:
        return "FROM_CLIENT"


# Usable in a def too: def list_repos(self, org: str = FROM_CLIENT, page: int = 1)
FROM_CLIENT = _FromClient()
