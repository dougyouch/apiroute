import importlib
import itertools
import sys
from pathlib import Path

import pytest

from apiroute.codegen.openapi.openapi_reader import OpenApiReader
from apiroute.codegen.package_emitter import PackageEmitter

FIXTURES = Path(__file__).parent / "fixtures"
_counter = itertools.count()


@pytest.fixture
def generate(tmp_path, monkeypatch):
    """generate(spec, models=True) writes a package from fixtures/<spec> and imports it.
    Each call gets its own package name, so imports never leak between tests."""
    monkeypatch.syspath_prepend(str(tmp_path))
    names = []

    def build(spec: str, models: bool = True, client_name: str = "ShopApi"):
        name = f"generated_{next(_counter)}"
        names.append(name)
        definition = OpenApiReader(str(FIXTURES / spec), client_name).read()
        PackageEmitter(definition, with_models=models).write(tmp_path / name)
        return importlib.import_module(name)

    yield build
    for module in [m for m in sys.modules if any(m.split(".")[0] == n for n in names)]:
        del sys.modules[module]
