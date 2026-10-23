import importlib
import itertools
import sys

import httpx
import pytest
from defusedxml.ElementTree import fromstring

from apiroute import AsyncHttpxClientTransport, HttpxClientTransport
from apiroute.codegen.package_emitter import PackageEmitter
from apiroute.codegen.wsdl.wsdl_reader import WsdlReader
from apiroute.soap import SoapFault
from tests.codegen.conftest import FIXTURES
from tests.conftest import needs_pydantic

ENV = "http://schemas.xmlsoap.org/soap/envelope/"
WS = "http://weather.test/ws"
GEO = "http://weather.test/geo"
_names = itertools.count()

FORECAST = f"""<s:Envelope xmlns:s="{ENV}"><s:Body>
<w:GetForecastResponse xmlns:w="{WS}" xmlns:g="{GEO}"><w:Forecast units="metric">
<g:Name>Paris</g:Name><w:Reading><w:Hour>9</w:Hour><w:Temperature unit="C">12.5</w:Temperature>
</w:Reading></w:Forecast></w:GetForecastResponse></s:Body></s:Envelope>"""

FAULT = f"""<s:Envelope xmlns:s="{ENV}"><s:Body><s:Fault><faultcode>s:Client</faultcode>
<faultstring>Unknown city</faultstring></s:Fault></s:Body></s:Envelope>"""


@pytest.fixture
def weather(tmp_path, monkeypatch):
    name = f"weather_{next(_names)}"
    definition = WsdlReader(str(FIXTURES / "weather.wsdl"), "WeatherApi").read()
    PackageEmitter(definition, with_models=True).write(tmp_path / name)
    monkeypatch.syspath_prepend(str(tmp_path))
    yield importlib.import_module(name)
    for module in [m for m in sys.modules if m.split(".")[0] == name]:
        del sys.modules[module]


@pytest.fixture
def api(weather, recorder):
    mock = httpx.MockTransport(recorder)
    return weather.WeatherApi(
        transport=HttpxClientTransport(httpx.Client(transport=mock)),
        async_transport=AsyncHttpxClientTransport(httpx.AsyncClient(transport=mock)),
    )


def sent_body(recorder):
    return fromstring(recorder.last.content).find(f"{{{ENV}}}Body")[0]


def test_dict_call_sends_an_envelope_and_reads_the_response(api, recorder):
    recorder.respond(httpx.Response(200, content=FORECAST.encode()))
    result = api.get_forecast(body={"City": "Paris", "Days": 2, "@units": "metric"})
    request = recorder.last
    assert str(request.url) == "https://weather.test/soap"
    assert request.headers["SOAPAction"] == '"http://weather.test/ws/GetForecast"'
    assert request.headers["Content-Type"] == "text/xml; charset=utf-8"
    element = sent_body(recorder)
    assert element.tag == f"{{{WS}}}GetForecast" and element.get("units") == "metric"
    assert [child.tag for child in element] == [f"{{{WS}}}City", f"{{{WS}}}Days"]
    assert result["Forecast"]["Reading"]["Temperature"] == {"@unit": "C", "#text": "12.5"}
    assert result["Forecast"][f"{{{GEO}}}Name"] == "Paris"


@needs_pydantic
def test_typed_call_round_trips_models(weather, api, recorder):
    recorder.respond(httpx.Response(200, content=FORECAST.encode()))
    models = importlib.import_module(f"{weather.__name__}.models.models")
    response = api.models.get_forecast(body=models.GetForecast(city="Paris", units="metric"))
    assert [child.tag for child in sent_body(recorder)] == [f"{{{WS}}}City"]  # unset Days left out
    forecast = response.forecast
    assert forecast.name == "Paris" and forecast.units == "metric"
    assert len(forecast.reading) == 1  # one <Reading> still makes a list
    assert forecast.reading[0].temperature.value == 12.5
    assert forecast.reading[0].temperature.unit == "C"


def test_faults_raise_soap_fault(api, recorder):
    recorder.respond(httpx.Response(500, content=FAULT.encode()))
    with pytest.raises(SoapFault, match="Unknown city") as raised:
        api.get_forecast(body={"City": "Atlantis"})
    assert raised.value.code == "s:Client"


@needs_pydantic
@pytest.mark.anyio
async def test_async_calls(api, recorder):
    recorder.respond(httpx.Response(200, content=FORECAST.encode()))
    response = await api.models.aio.get_forecast(body={"City": "Paris"})
    assert response.forecast.name == "Paris"
