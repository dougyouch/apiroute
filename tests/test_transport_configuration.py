import httpx

from apiroute import Client, HttpxClientTransport, route, use_transport


class Api(Client):
    base_url = "https://x.test"

    @route("/things")
    def get_things(self): ...


def test_use_transport_for_a_class_reaches_its_requests(recorder):
    use_transport(HttpxClientTransport(httpx.Client(transport=httpx.MockTransport(recorder))), Api)
    Api().get_things()
    assert str(recorder.last.url) == "https://x.test/things"


def test_an_instance_transport_wins_over_the_registry(recorder, transport):
    use_transport(
        HttpxClientTransport(httpx.Client(transport=httpx.MockTransport(lambda r: 1 / 0)))
    )
    Api(transport=transport).get_things()
    assert len(recorder.requests) == 1
