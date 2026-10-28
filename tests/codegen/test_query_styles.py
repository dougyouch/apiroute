import urllib.parse

import httpx

from apiroute import HttpxClientTransport


def test_deep_object_parameters_get_bracketed_names_and_others_stay_flat(generate, recorder):
    filters = generate("filters.yaml", client_name="FiltersApi")
    transport = HttpxClientTransport(httpx.Client(transport=httpx.MockTransport(recorder)))
    api = filters.FiltersApi(transport=transport)
    recorder.respond(httpx.Response(200, json={}), httpx.Response(200, json={}))
    api.charges.list_charges(created={"gt": 1, "lte": 9}, expand=["customer"])
    assert urllib.parse.unquote(recorder.last.url.query.decode()) == (
        "created[gt]=1&created[lte]=9&expand[]=customer"
    )
    api.tags.list_tags(name=["a", "b"])  # a form-style array, as before
    assert recorder.last.url.query == b"name=a&name=b"
