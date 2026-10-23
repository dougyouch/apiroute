import threading

from apiroute import Client, namespace, route
from apiroute.namespace import current_prefix


def test_prefixes_routes_declared_inside_and_nests():
    class Api(Client):
        with namespace("/admin"):
            list_users = route("/users")

            with namespace("/v2"):

                @route("/teams/{id}")
                def get_team(self, id): ...

        get_status = route("/status")

    paths = {
        name: vars(Api)[name].definition.path.source
        for name in ("list_users", "get_team", "get_status")
    }
    assert paths == {
        "list_users": "/admin/users",
        "get_team": "/admin/v2/teams/{id}",
        "get_status": "/status",
    }


def test_the_prefix_is_cleared_after_an_error():
    try:
        with namespace("/x"):
            raise RuntimeError
    except RuntimeError:
        pass
    assert current_prefix() == ""


def test_prefixes_are_per_thread():
    seen = []
    with namespace("/main"):
        thread = threading.Thread(target=lambda: seen.append(current_prefix()))
        thread.start()
        thread.join()
    assert seen == [""]
