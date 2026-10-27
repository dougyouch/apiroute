# mypy: disable-error-code="empty-body"
"""Checked by mypy in test_static_types.py, never run: each line marked E must be an error."""

from apiroute import Client, route


class Api(Client):
    @route("/users/{name}")
    def get_user(self, name: str) -> dict[str, int]: ...


api = Api()
api.get_user(123)  # E: arg-type
api.get_user("octo", nope=1)  # E: call-arg
api.get_user()  # E: call-arg
name: str = api.get_user("octo")  # E: assignment
api.get_user("octo").missing  # noqa: B018  # E: attr-defined
