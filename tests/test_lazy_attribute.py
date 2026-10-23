import importlib
import sys
import textwrap

import pytest

FILES = {
    "lazypkg/__init__.py": "from .client import Api\n",
    "lazypkg/client.py": """
        from apiroute import Client, lazy, route

        class Api(Client):
            base_url = "https://x.test"
            issues = lazy(".issues.client", "Issues")
            models = lazy(".models.client", "ApiModels")

            @route("/status")
            def get_status(self): ...
    """,
    "lazypkg/issues/__init__.py": "",
    "lazypkg/issues/client.py": """
        from apiroute import Section, route

        class Issues(Section):
            @route("/issues/{id}")
            def get(self, id): ...
    """,
    "lazypkg/models/__init__.py": "",
    "lazypkg/models/client.py": """
        from apiroute import TypedClient
        from .models import Status

        class ApiModels(TypedClient):
            def get_status(self) -> Status:
                return self._call("get_status", Status)
    """,
    "lazypkg/models/models.py": """
        from pydantic import BaseModel

        class Status(BaseModel):
            ok: bool
    """,
}


@pytest.fixture
def lazypkg(tmp_path, monkeypatch):
    for path, source in FILES.items():
        file = tmp_path / path
        file.parent.mkdir(parents=True, exist_ok=True)
        file.write_text(textwrap.dedent(source))
    monkeypatch.syspath_prepend(str(tmp_path))
    yield importlib.import_module("lazypkg")
    for name in [name for name in sys.modules if name.startswith("lazypkg")]:
        del sys.modules[name]


def test_nothing_beyond_the_root_is_imported_until_used(lazypkg, transport):
    api = lazypkg.Api(transport=transport)
    api.get_status()
    assert "lazypkg.issues.client" not in sys.modules
    assert "lazypkg.models.client" not in sys.modules


def test_a_lazy_section_loads_and_is_cached(lazypkg, transport, recorder):
    api = lazypkg.Api(transport=transport)
    api.issues.get(3)
    assert str(recorder.last.url) == "https://x.test/issues/3"
    assert api.issues is api.issues
    assert "lazypkg.issues.client" in sys.modules


def test_the_class_attribute_names_the_class(lazypkg):
    assert lazypkg.Api.issues.__name__ == "Issues"


def test_options_and_aio_reach_lazy_sections(lazypkg, transport, recorder):
    lazypkg.Api(transport=transport).with_options(query={"q": "1"}).issues.get(1)
    assert recorder.last.url.params["q"] == "1"
