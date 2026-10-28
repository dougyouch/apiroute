import importlib

import pytest

from apiroute.codegen.api_definition import ApiDefinition, Group, Model, ModelField
from apiroute.codegen.cli import main
from apiroute.codegen.open_enums import OpenEnums, opened
from apiroute.codegen.type_ref import TypeRef
from tests.conftest import needs_pydantic


@pytest.mark.parametrize(
    ("expr", "expected"),
    [
        ("Literal['N', 'S'] | None", "Literal['N', 'S'] | str | None"),
        ("list[Literal['a', 'b']]", "list[Literal['a', 'b'] | str]"),
        ("Literal[1, 2, 3]", "Literal[1, 2, 3] | int"),
        ("dict[str, Literal['x', 'y']] | Pet", "dict[str, Literal['x', 'y'] | str] | Pet"),
        ("Literal['Feature']", "Literal['Feature']"),  # a union member's tag stays closed
        ("Literal['a', 1]", "Literal['a', 1]"),
        ("Literal[True, False]", "Literal[True, False]"),
        ("str | None", "str | None"),
    ],
)
def test_enums_of_two_or_more_values_open(expr, expected):
    assert opened(TypeRef(expr, frozenset({"Pet"}))) == TypeRef(expected, frozenset({"Pet"}))


def test_fields_and_aliases_are_opened():
    period = Model(
        "Period",
        fields=[
            ModelField("wind", None, TypeRef("Literal['N', 'S'] | None"), required=False),
            ModelField("name", None, TypeRef("str"), required=True),
        ],
    )
    status = Model("Status", alias_of=TypeRef("Literal['open', 'closed']"))
    definition = ApiDefinition(
        client_name="Api",
        base_url="https://api.test",
        title="",
        description="",
        source="spec.yaml",
        root=Group("", "Api"),
        models={"Period": period, "Status": status},
    )
    OpenEnums().apply(definition)
    assert [f.type.expr for f in period.fields] == ["Literal['N', 'S'] | str | None", "str"]
    assert status.alias_of.expr == "Literal['open', 'closed'] | str"


SPEC = """\
openapi: 3.0.0
info: {title: Weather, version: "1"}
servers: [{url: "https://weather.test"}]
paths:
  /forecast:
    get:
      operationId: forecast
      responses:
        "200":
          description: ok
          content:
            application/json:
              schema:
                type: object
                properties:
                  windDirection: {type: string, enum: [N, E, S, W]}
"""


@needs_pydantic
def test_generated_models_accept_unlisted_values(tmp_path, monkeypatch):
    spec = tmp_path / "weather.yaml"
    spec.write_text(SPEC)
    out = tmp_path / "open_weather"
    assert main(["generate", "openapi", str(spec), "-o", str(out), "--models", "--open-enums"]) == 0
    monkeypatch.syspath_prepend(str(tmp_path))
    response = importlib.import_module("open_weather.models.schemas.forecast_response")
    response = response.ForecastResponse
    assert response.model_validate({"windDirection": "N"}).wind_direction == "N"
    assert response.model_validate({"windDirection": ""}).wind_direction == ""
