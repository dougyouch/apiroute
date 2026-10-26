import shutil
import subprocess

import pytest

from apiroute.codegen.cli import main
from tests.codegen.conftest import FIXTURES


def test_generates_a_package(tmp_path, capsys):
    out = tmp_path / "shop"
    assert (
        main(
            [
                "generate",
                "openapi",
                str(FIXTURES / "shop.yaml"),
                "-o",
                str(out),
                "--models",
                "--no-format",
            ]
        )
        == 0
    )
    assert "9 operations, 11 models" in capsys.readouterr().out
    assert "class ShopApi(Client)" in (out / "client.py").read_text()


def test_default_client_name_comes_from_the_output_directory(tmp_path):
    main(
        [
            "generate",
            "openapi",
            str(FIXTURES / "swagger2.json"),
            "-o",
            str(tmp_path / "legacy"),
            "--no-format",
        ]
    )
    assert "class LegacyApi(Client)" in (tmp_path / "legacy" / "client.py").read_text()


def test_errors_are_reported_without_a_traceback(tmp_path, capsys):
    assert (
        main(["generate", "openapi", str(tmp_path / "missing.yaml"), "-o", str(tmp_path / "x")])
        == 1
    )
    assert capsys.readouterr().err.startswith("apiroute: FileNotFoundError")


RELATIVE_SERVER = """
openapi: 3.0.1
info:
  title: Relative
  version: "1"
  description: The whole API's long description.
servers:
  - url: /api/v2
paths:
  /things:
    get:
      tags: [things]
      responses:
        "200":
          description: ok
  /status:
    get:
      responses:
        "200":
          description: ok
"""


def _generate_relative(tmp_path, *extra):
    spec = tmp_path / "relative.yaml"
    spec.write_text(RELATIVE_SERVER)
    out = tmp_path / "rel"
    code = main(["generate", "openapi", str(spec), "-o", str(out), "--no-format", *extra])
    return code, out


def test_base_url_sets_the_root_clients_host_for_a_relative_server(tmp_path):
    code, out = _generate_relative(tmp_path, "--base-url", "https://api.example.test/api/v2/")
    assert code == 0
    assert 'base_url = "https://api.example.test/api/v2"' in (out / "client.py").read_text()


def test_a_relative_server_in_a_file_leaves_base_url_unset_without_the_option(tmp_path):
    code, out = _generate_relative(tmp_path)
    assert code == 0 and "base_url" not in (out / "client.py").read_text()


def test_an_invalid_base_url_is_reported(tmp_path, capsys):
    code, _ = _generate_relative(tmp_path, "--base-url", "file:///etc")
    assert code == 1 and "ValueError" in capsys.readouterr().err


def test_a_section_without_a_tag_description_does_not_repeat_the_apis(tmp_path):
    _, out = _generate_relative(tmp_path)
    assert "The whole API's long description." in (out / "client.py").read_text()
    assert "The whole API's long description." not in (out / "things" / "client.py").read_text()


def test_a_section_without_models_imports_no_lazy(tmp_path):
    _, out = _generate_relative(tmp_path)
    section = (out / "things" / "client.py").read_text()
    assert (
        "from apiroute import Section, route" in section and "lazy" not in section.split('"""')[0]
    )


@pytest.mark.parametrize("formatting", [[], ["--no-format"]])
def test_the_base_class_import_is_a_first_party_block_of_its_own(tmp_path, formatting):
    _, out = _generate_relative(tmp_path, "--base-class", "mypkg.auth:Auth", *formatting)
    text = (out / "client.py").read_text()
    assert "from apiroute import lazy, route\n\nfrom mypkg.auth import Auth\n" in text


@pytest.mark.skipif(shutil.which("ruff") is None, reason="ruff not installed")
def test_formatted_output_passes_ruff_with_the_base_package_first_party(tmp_path):
    _, out = _generate_relative(tmp_path, "--base-class", "mypkg.auth:Auth")
    check = subprocess.run(
        [
            "ruff",
            "check",
            "--isolated",
            "--line-length=100",
            "--select=E,F,I",
            "--config",
            'lint.isort.known-first-party = ["mypkg"]',
            "--config",
            'lint.isort.known-third-party = ["apiroute"]',  # as in any project that installs it
            str(out),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert check.returncode == 0, check.stdout
