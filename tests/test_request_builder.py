from apiroute import Client, Header, Query, route
from apiroute.request_builder import RequestBuilder
from apiroute.request_options import RequestOptions


class Api(Client):
    base_url = "https://x.test/v1/"
    headers = {"Accept": "application/json", "X-Token": lambda self: self.token}
    query_params = {"key": "k"}
    token = "t1"
    account_id = 42

    @route("/accounts/{account_id}/users/{id}", query={"expand": "{expand}"})
    def get_user(self, id, expand=None, trace: Header("X-Trace") = None, page: Query = None): ...

    @route("/users", body={"user": {"name": "{name}", "age": "{age}"}})
    def create_user(self, name, age): ...

    @route("POST", "/raw", body="<ping/>")
    def ping(self): ...

    @route("/users/{id}")
    def update_user(self, id, body): ...


def build(route_name, options=None, **values):
    client = Api()
    definition = vars(Api)[route_name].definition
    options = options or RequestOptions()
    return RequestBuilder(client._request_config(), client, options).build(definition, values)


def test_url_query_and_headers():
    spec = build("get_user", id="a b", expand="teams", trace="abc", page=2)
    assert spec.method == "GET"
    assert spec.url == "https://x.test/v1/accounts/42/users/a%20b"
    assert spec.params == [("key", "k"), ("expand", "teams"), ("page", "2")]
    assert spec.headers == {"Accept": "application/json", "X-Token": "t1", "X-Trace": "abc"}
    assert spec.content is None
    assert spec.timeout == 30.0


def test_none_values_are_left_out():
    spec = build("get_user", id=1, expand=None, trace=None, page=None)
    assert spec.params == [("key", "k")]
    assert "X-Trace" not in spec.headers


def test_json_body_keeps_types_and_sets_content_type():
    spec = build("create_user", name="Ann", age=30)
    assert spec.content == b'{"user": {"name": "Ann", "age": 30}}'
    assert spec.headers["Content-Type"] == "application/json"


def test_literal_string_body_is_sent_as_is():
    assert build("ping").content == "<ping/>"


def test_options_override_case_insensitively_and_none_drops():
    options = RequestOptions(
        headers={"accept": "text/plain", "X-Token": None}, query={"key": None}, timeout=2
    )
    spec = build("get_user", options, id=1, expand=None, trace=None, page=None)
    assert spec.headers == {"accept": "text/plain"}
    assert spec.params == []
    assert spec.timeout == 2


def test_options_body_is_merged_shallowly_over_the_route_body():
    spec = build("create_user", RequestOptions(body={"source": "api"}), name="Ann", age=30)
    assert spec.content == b'{"user": {"name": "Ann", "age": 30}, "source": "api"}'


def test_options_body_replaces_nested_dicts_whole():
    spec = build("create_user", RequestOptions(body={"user": {"name": "Bob"}}), name="Ann", age=30)
    assert spec.content == b'{"user": {"name": "Bob"}}'


def test_none_in_options_body_removes_the_key():
    options = RequestOptions(body={"user": None, "dry_run": True})
    assert build("create_user", options, name="Ann", age=30).content == b'{"dry_run": true}'


def test_options_body_merges_over_a_body_argument():
    options = RequestOptions(body={"b": 3})
    spec = build("update_user", options, id=1, body={"a": 1, "b": 2})
    assert spec.content == b'{"a": 1, "b": 3}'


def test_options_body_replaces_a_non_dict_body():
    spec = build("ping", RequestOptions(body={"a": 1}))
    assert spec.content == b'{"a": 1}'
    assert spec.headers["Content-Type"] == "application/json"


def test_options_body_is_sent_when_the_route_has_none():
    spec = build(
        "get_user", RequestOptions(body={"a": 1}), id=1, expand=None, trace=None, page=None
    )
    assert spec.content == b'{"a": 1}'


def test_options_url_replaces_the_base_url_path_and_query():
    options = RequestOptions(url="https://x.test/v1/users/7?expand=all&page=2")
    spec = build("get_user", options, id=1, expand="none", page=1)
    assert spec.url == "https://x.test/v1/users/7"
    assert spec.params == [("key", "k"), ("expand", "all"), ("page", "2")]
    assert spec.headers["X-Token"] == "t1"


def test_options_url_carrying_the_client_query_keeps_its_own_value():
    spec = build("get_user", RequestOptions(url="https://x.test/v1/users?key=other"), id=1)
    assert spec.params == [("key", "other")]
