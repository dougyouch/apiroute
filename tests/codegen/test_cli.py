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


GRAPHQL_SCHEMA = str(FIXTURES / "graphql" / "schema.graphql")
GRAPHQL_OPS = str(FIXTURES / "graphql" / "ops")


def _graphql(out, *extra):
    return main(
        [
            "generate",
            "graphql",
            GRAPHQL_SCHEMA,
            "--operations",
            GRAPHQL_OPS,
            "-o",
            str(out),
            "--no-format",
            *extra,
        ]
    )


def test_generates_a_graphql_package(tmp_path, capsys):
    out = tmp_path / "hub"
    assert _graphql(out, "--models", "--endpoint", "https://api.hub.test/graphql") == 0
    assert "4 operations, 20 models" in capsys.readouterr().out
    client = (out / "client.py").read_text()
    assert "class HubApi(Client)" in client
    assert 'base_url = "https://api.hub.test"' in client


def test_graphql_warnings_are_printed(tmp_path, capsys):
    ops = tmp_path / "ops"
    ops.mkdir()
    (ops / "a.graphql").write_text("query A { viewer { oldLogin } }")
    assert (
        main(
            [
                "generate",
                "graphql",
                GRAPHQL_SCHEMA,
                "--operations",
                str(ops),
                "-o",
                str(tmp_path / "out"),
                "--no-format",
            ]
        )
        == 0
    )
    err = capsys.readouterr().err
    assert err.startswith(f"apiroute: warning: {ops}/a.graphql:1:")
    assert "User.oldLogin is deprecated" in err


def test_invalid_operations_leave_the_output_untouched(tmp_path, capsys):
    out = tmp_path / "hub"
    assert _graphql(out) == 0
    before = {p: p.read_text() for p in out.rglob("*.py")}
    ops = tmp_path / "ops"
    ops.mkdir()
    (ops / "a.graphql").write_text("query A { viewer { logn } }\nquery B { viewr { id } }")
    arguments = ["generate", "graphql", GRAPHQL_SCHEMA, "--operations", str(ops), "-o", str(out)]
    assert main(arguments) == 1
    err = capsys.readouterr().err
    assert err.startswith("apiroute: ValueError: the operations don't match the schema:")
    assert err.count(f"{ops}/a.graphql:") == 2
    assert {p: p.read_text() for p in out.rglob("*.py")} == before


@pytest.mark.parametrize(
    "extra, message",
    [
        (["--base-url", "https://x.test"], "takes --endpoint, not --base-url"),
        (["--header", "no colon"], "--header takes 'Name: value'"),
        (["--scalar", "DateTime"], "--scalar takes NAME=MODULE:TYPE"),
    ],
)
def test_graphql_option_errors(tmp_path, capsys, extra, message):
    assert _graphql(tmp_path / "hub", *extra) == 1
    assert message in capsys.readouterr().err


def test_graphql_needs_operations(tmp_path, capsys):
    assert main(["generate", "graphql", GRAPHQL_SCHEMA, "-o", str(tmp_path / "x")]) == 1
    assert "needs --operations DIR" in capsys.readouterr().err


def test_operations_only_apply_to_graphql(tmp_path, capsys):
    arguments = ["generate", "openapi", str(FIXTURES / "shop.yaml"), "-o", str(tmp_path / "x")]
    assert main([*arguments, "--operations", GRAPHQL_OPS]) == 1
    assert "--operations only applies to graphql" in capsys.readouterr().err


def _introspection_response(status=200):
    import graphql
    import httpx

    schema = graphql.build_schema((FIXTURES / "graphql" / "schema.graphql").read_text())
    data = graphql.graphql_sync(schema, graphql.get_introspection_query()).data
    return httpx.Response(
        status, json={"data": data}, request=httpx.Request("POST", "https://x.test")
    )


@pytest.fixture
def introspection(monkeypatch):
    """Answers fetch-schema's POST; .status sets the status, .headers records what was sent."""
    import apiroute.codegen.graphql.schema_fetcher as fetcher

    class Endpoint:
        status = 200
        headers: dict = {}

    def post(url, json, headers, **kwargs):
        Endpoint.headers = headers
        return _introspection_response(Endpoint.status)

    monkeypatch.setattr(fetcher.httpx, "post", post)
    return Endpoint


def test_fetch_schema_writes_sdl(tmp_path, capsys, introspection):
    out = tmp_path / "schema.graphql"
    arguments = [
        "fetch-schema",
        "https://x.test/graphql",
        "-o",
        str(out),
        "-H",
        "Authorization: Bearer t",
    ]
    assert main(arguments) == 0
    assert introspection.headers == {"Authorization": "Bearer t"}
    text = out.read_text()
    assert "type Repository implements Node" in text
    assert '"""The user\'s display name."""' in text  # descriptions come along
    assert f"to {out}" in capsys.readouterr().out
    hub = tmp_path / "hub"
    generate = ["generate", "graphql", str(out), "--operations", GRAPHQL_OPS, "-o", str(hub)]
    assert main([*generate, "--no-format"]) == 0


def test_fetch_schema_writes_json(tmp_path, introspection):
    import json

    out = tmp_path / "schema.json"
    assert main(["fetch-schema", "https://x.test/graphql", "-o", str(out)]) == 0
    assert "__schema" in json.loads(out.read_text())["data"]


def test_fetch_schema_failures_write_nothing(tmp_path, capsys, introspection):
    introspection.status = 401
    out = tmp_path / "schema.graphql"
    assert main(["fetch-schema", "https://x.test/graphql", "-o", str(out)]) == 1
    assert "answered HTTP 401" in capsys.readouterr().err
    assert not out.exists()
