import importlib
import pathlib
import sys
import textwrap

import httpx
import pytest
from defusedxml.ElementTree import fromstring

from apiroute import HttpxClientTransport
from apiroute.codegen.openapi.openapi_reader import OpenApiReader
from apiroute.codegen.package_emitter import PackageEmitter
from apiroute.codegen.wsdl.wsdl_reader import WsdlReader
from tests.codegen.conftest import FIXTURES

AUTH = '''
    from apiroute import Client


    class ShopAuth(Client):
        """Hand-written: regenerating the client never touches it."""

        headers = {"Authorization": lambda self: f"Token {self.secret}"}

        def __init__(self, secret, **kwargs):
            super().__init__(**kwargs)
            self.secret = secret


    class TradingAuth(Client):
        """eBay Trading style: credentials in the SOAP header, the call name in the query."""

        def __init__(self, token, **kwargs):
            super().__init__(**kwargs)
            self.token = token

        def soap_header(self, operation):
            return {"Credentials": {"Token": self.token}}

        def on_request(self, request):
            from dataclasses import replace
            return replace(request, params=[*request.params, ("callname", request.operation)])
'''


@pytest.fixture
def build(tmp_path, monkeypatch):
    (tmp_path / "myauth.py").write_text(textwrap.dedent(AUTH))
    monkeypatch.syspath_prepend(str(tmp_path))
    names = []

    def generate(reader, name):
        definition = reader.read()
        definition.base_class = (
            "myauth:ShopAuth" if name.startswith("shop") else "myauth:TradingAuth"
        )
        PackageEmitter(definition, with_models=False).write(tmp_path / name)
        names.append(name)
        return importlib.import_module(name)

    yield generate
    for module in [m for m in sys.modules if m.split(".")[0] in {*names, "myauth"}]:
        del sys.modules[module]


def test_the_root_extends_the_base_class_and_skips_spec_auth(build, recorder):
    shop = build(OpenApiReader(str(FIXTURES / "shop.yaml"), "ShopApi"), "shop_base")
    source = sys.modules["shop_base.client"].__file__
    text = open(source).read()
    assert "from myauth import ShopAuth" in text and "class ShopApi(ShopAuth):" in text
    assert "def __init__" not in text and "Bearer" not in text
    api = shop.ShopApi(
        "s3cret",
        transport=HttpxClientTransport(httpx.Client(transport=httpx.MockTransport(recorder))),
    )
    api.pets.get_pet(1)  # a section: the base class's headers reach it
    assert recorder.last.headers["Authorization"] == "Token s3cret"


def test_operation_ids_are_kept_for_hooks(build):
    package = build(OpenApiReader(str(FIXTURES / "shop.yaml"), "ShopApi"), "shop_ops")
    text = (pathlib.Path(package.__file__).parent / "pets" / "client.py").read_text()
    assert 'operation="Pets_getPet"' in text  # the method is get_pet


def test_wsdl_clients_get_soap_headers_and_operation_names(build, recorder):
    weather = build(WsdlReader(str(FIXTURES / "weather.wsdl"), "WeatherApi"), "weather_base")
    recorder.respond(
        httpx.Response(
            200,
            content=(
                b'<s:Envelope xmlns:s="http://schemas.xmlsoap.org/soap/envelope/"><s:Body>'
                b'<PingResponse xmlns="http://weather.test/ws">pong</PingResponse></s:Body></s:Envelope>'
            ),
        )
    )
    api = weather.WeatherApi(
        "t0k", transport=HttpxClientTransport(httpx.Client(transport=httpx.MockTransport(recorder)))
    )
    assert api.ping() == "pong"
    request = recorder.last
    assert request.url.params["callname"] == "Ping"
    envelope = fromstring(request.content)
    token = envelope.find(".//{http://weather.test/ws}Token")
    assert token is not None and token.text == "t0k"


def test_a_malformed_base_class_is_reported():
    definition = OpenApiReader(str(FIXTURES / "shop.yaml"), "ShopApi").read()
    definition.base_class = "not a path"
    with pytest.raises(ValueError, match="package.module:Class"):
        PackageEmitter(definition, with_models=False).files()
