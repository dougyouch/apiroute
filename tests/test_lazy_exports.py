import sys
import types

import pytest

from apiroute import lazy_exports


@pytest.fixture
def package(tmp_path, monkeypatch):
    (tmp_path / "lazyexp").mkdir()
    (tmp_path / "lazyexp" / "__init__.py").write_text("")
    (tmp_path / "lazyexp" / "thing.py").write_text("class Thing:\n    pass\n")
    monkeypatch.syspath_prepend(str(tmp_path))
    index = types.ModuleType("lazyexp.index")
    index.__package__ = "lazyexp"
    sys.modules["lazyexp.index"] = index
    index.__getattr__, index.__dir__ = lazy_exports("lazyexp.index", {"Thing": ".thing"})
    yield index
    for name in [n for n in sys.modules if n.startswith("lazyexp")]:
        del sys.modules[name]


def test_imports_on_first_access_and_caches(package):
    assert "lazyexp.thing" not in sys.modules
    assert package.Thing.__name__ == "Thing"
    assert "lazyexp.thing" in sys.modules
    assert "Thing" in vars(package)  # cached; __getattr__ isn't consulted again


def test_unknown_names_and_dir(package):
    with pytest.raises(AttributeError, match="Other"):
        package.Other  # noqa: B018
    assert "Thing" in dir(package)
