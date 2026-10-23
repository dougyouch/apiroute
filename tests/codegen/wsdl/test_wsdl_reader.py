import pytest

from apiroute.codegen.wsdl.wsdl_reader import WsdlReader
from tests.codegen.conftest import FIXTURES


def read():
    return WsdlReader(str(FIXTURES / "weather.wsdl"), "WeatherApi").read()


def test_prefers_the_soap_11_port():
    definition = read()
    assert definition.base_url == "https://weather.test/soap"
    forecast, ping = definition.root.operations
    assert forecast.soap.version == "1.1"
    assert forecast.headers == {"SOAPAction": '"http://weather.test/ws/GetForecast"'}
    assert forecast.summary == "The forecast for a city."
    assert (forecast.method, forecast.path, forecast.name, ping.name) == (
        "POST",
        "",
        "get_forecast",
        "ping",
    )


def test_types_follow_the_xsd():
    models = read().models
    request = {f.name: f for f in models["GetForecast"].fields}
    assert (request["city"].alias, request["city"].required) == ("City", True)
    assert (request["days"].type.expr, request["days"].required) == ("int", False)
    assert request["units"].alias == "@units"
    forecast = {f.name: f for f in models["Forecast"].fields}
    assert list(forecast) == ["name", "latitude", "summary", "reading", "units"]  # base first
    assert forecast["name"].alias == "{http://weather.test/geo}Name"  # from the imported schema
    assert forecast["reading"].type.expr == "Annotated[list[Reading], BeforeValidator(as_list)]"
    measure = {f.name: f for f in models["Measure"].fields}
    assert measure["value"].alias == "#text" and measure["value"].type.expr == "float"
    assert models["Units"].alias_of.expr == "Literal['metric', 'imperial']"


def test_rpc_style_is_refused(tmp_path):
    rpc = (FIXTURES / "weather.wsdl").read_text().replace('style="document"', 'style="rpc"')
    (tmp_path / "rpc.wsdl").write_text(rpc)
    (tmp_path / "geo.xsd").write_text((FIXTURES / "geo.xsd").read_text())
    with pytest.raises(ValueError, match="rpc-style"):
        WsdlReader(str(tmp_path / "rpc.wsdl"), "Api").read()
