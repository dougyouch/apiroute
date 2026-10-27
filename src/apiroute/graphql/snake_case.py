import re

_BOUNDARY = re.compile(r"(?<=[a-z0-9])(?=[A-Z])|(?<=[A-Z])(?=[A-Z][a-z])")


def snake_case(name: str) -> str:
    """repoName -> repo_name, userID -> user_id, HTMLUrl -> html_url."""
    return _BOUNDARY.sub("_", name).lower()
