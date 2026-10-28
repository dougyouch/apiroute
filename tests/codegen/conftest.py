import importlib
import itertools
import sys
from pathlib import Path

import pytest

from apiroute.codegen.graphql.graphql_reader import GraphQLReader
from apiroute.codegen.openapi.openapi_reader import OpenApiReader
from apiroute.codegen.operation_names import OperationNames
from apiroute.codegen.package_emitter import PackageEmitter

FIXTURES = Path(__file__).parent / "fixtures"
_counter = itertools.count()


@pytest.fixture
def generate(tmp_path, monkeypatch):
    """generate(spec, models=True) writes a package from fixtures/<spec> and imports it,
    with operation_names (operation ID -> dotted name) applied if given. Each call gets its
    own package name, so imports never leak between tests."""
    monkeypatch.syspath_prepend(str(tmp_path))
    names = []

    def build(
        spec: str,
        models: bool = True,
        client_name: str = "ShopApi",
        operation_names: dict[str, str] | None = None,
    ):
        name = f"generated_{next(_counter)}"
        names.append(name)
        definition = OpenApiReader(str(FIXTURES / spec), client_name).read()
        if operation_names:
            OperationNames(operation_names).apply(definition)
        PackageEmitter(definition, with_models=models).write(tmp_path / name)
        return importlib.import_module(name)

    yield build
    for module in [m for m in sys.modules if any(m.split(".")[0] == n for n in names)]:
        del sys.modules[module]


GRAPHQL = FIXTURES / "graphql"


@pytest.fixture
def generate_graphql(tmp_path, monkeypatch):
    """generate_graphql(models=True, **reader_options) writes a package from fixtures/graphql
    (schema.graphql and ops/) and imports it, under its own package name."""
    monkeypatch.syspath_prepend(str(tmp_path))
    names = []

    def build(models: bool = True, operations: str = str(GRAPHQL / "ops"), **options):
        name = f"generated_graphql_{next(_counter)}"
        names.append(name)
        options.setdefault("endpoint", "https://api.hub.test/graphql")
        options.setdefault("scalars", {"DateTime": ("datetime", "datetime")})
        reader = GraphQLReader(str(GRAPHQL / "schema.graphql"), operations, "HubApi", **options)
        PackageEmitter(reader.read(), with_models=models).write(tmp_path / name)
        return importlib.import_module(name)

    yield build
    for module in [m for m in sys.modules if any(m.split(".")[0] == n for n in names)]:
        del sys.modules[module]
