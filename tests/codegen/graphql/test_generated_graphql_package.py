import asyncio
import datetime
import inspect
import shutil
import subprocess
import sys

import pytest

from apiroute.codegen.cli import main
from apiroute.codegen.graphql.graphql_reader import GraphQLReader
from apiroute.codegen.package_emitter import PackageEmitter
from apiroute.testing import MockTransport, graphql_response
from tests.codegen.conftest import GRAPHQL
from tests.conftest import needs_pydantic

VIEWER = {"id": "1", "login": "octo", "createdAt": "2026-01-02T03:04:05Z", "url": "https://u"}


@pytest.fixture
def hub(generate_graphql):
    return generate_graphql()


@pytest.fixture
def mock():
    return MockTransport()


@pytest.fixture
def api(hub, mock):
    return hub.HubApi(transport=mock, async_transport=mock.aio)


def test_sections_and_models_load_on_first_use(hub, api):
    assert f"{hub.__name__}.repos.client" not in sys.modules
    api.repos  # noqa: B018
    assert f"{hub.__name__}.repos.client" in sys.modules
    assert f"{hub.__name__}.models.client" not in sys.modules


def test_dict_signatures(api):
    def shape(method):
        return [
            (p.name, p.kind.name, p.default) for p in inspect.signature(method).parameters.values()
        ]

    assert shape(api.search) == [
        ("query", "KEYWORD_ONLY", inspect.Parameter.empty),
        ("type_", "KEYWORD_ONLY", inspect.Parameter.empty),
        ("from_", "KEYWORD_ONLY", None),
    ]
    assert shape(api.repos.star) == [("input", "KEYWORD_ONLY", inspect.Parameter.empty)]


def test_a_dict_call_sends_the_document_and_variables(api, mock):
    mock.respond(graphql_response(data={"search": []}))
    assert api.search(query="q", type_="USER", from_=5) == {"search": []}
    call = mock.last
    assert str(call.url) == "https://api.hub.test/graphql"
    assert call.operation == "Search"
    assert call.json()["query"].startswith("query Search($query: String!")
    assert call.json()["query"].endswith("}")
    assert "__typename" in call.json()["query"]
    assert call.graphql_variables == {"query": "q", "type": "USER", "from": 5}


def test_a_section_call_includes_its_fragments(api, mock):
    mock.respond(graphql_response(data={"repository": None}))
    api.repos.repository(owner="o", repo_name="r")
    sent = mock.last.json()
    assert (
        sent["query"]
        .rstrip()
        .endswith("fragment RepoFields on Repository {\n  name\n  stargazerCount\n  visibility\n}")
    )
    assert sent["variables"] == {"owner": "o", "repoName": "r"}


@needs_pydantic
def test_typed_results_with_unions_and_custom_scalars(api, mock):
    mock.respond(
        graphql_response(
            data={
                "search": [
                    {"__typename": "User", "login": "a"},
                    {"__typename": "Repository", "name": "r"},
                    {"__typename": "Organization"},
                ]
            }
        )
    )
    result = api.models.search(query="q", type_="USER")
    assert [type(item).__name__ for item in result.search] == [
        "SearchSearchUser",
        "SearchSearchRepository",
        "SearchSearchOther",
    ]
    assert result.search[0].login == "a"
    mock.respond(graphql_response(data={"viewer": VIEWER}))
    viewer = api.models.viewer().viewer
    assert viewer.created_at == datetime.datetime(2026, 1, 2, 3, 4, 5, tzinfo=datetime.timezone.utc)
    assert viewer.name is None  # @include(if: $full), not requested


@needs_pydantic
def test_typed_inputs_are_sent_by_wire_name(hub, api, mock):
    models = __import__(f"{hub.__name__}.repos.models.models", fromlist=["AddStarInput"])
    tag = models.StarTag(name="t", parent=models.StarTag(name="p"))
    mock.respond(graphql_response(data={"addStar": {"clientMutationId": None, "starrable": None}}))
    result = api.repos.models.star(input=models.AddStarInput(starrable_id="s", tags=[tag]))
    assert result.add_star.starrable is None
    assert mock.last.graphql_variables == {
        "input": {"starrableId": "s", "tags": [{"name": "t", "parent": {"name": "p"}}]}
    }


@needs_pydantic
def test_typed_calls_through_aio(api, mock):
    mock.respond(graphql_response(data={"viewer": VIEWER}))
    assert asyncio.run(api.models.aio.viewer()).viewer.login == "octo"


def test_a_mutation_isnt_retried_after_a_read_timeout(hub, mock):
    import httpx

    from apiroute import Retries

    class Retrying(hub.HubApi):
        retries = Retries(attempts=3, sleep=0)

    mock.respond(httpx.ReadTimeout("slow"))
    with pytest.raises(httpx.ReadTimeout):
        Retrying(transport=mock).repos.star(input={"starrableId": "s"})
    assert len(mock.calls) == 1


def test_generating_twice_gives_identical_files():
    def files():
        reader = GraphQLReader(str(GRAPHQL / "schema.graphql"), str(GRAPHQL / "ops"), "HubApi")
        return PackageEmitter(reader.read(), with_models=True).files()

    assert files() == files()


@pytest.mark.skipif(shutil.which("ruff") is None, reason="ruff not installed")
def test_formatted_output_passes_ruff(tmp_path):
    out = tmp_path / "hub"
    arguments = ["generate", "graphql", str(GRAPHQL / "schema.graphql"), "-o", str(out)]
    arguments += ["--operations", str(GRAPHQL / "ops"), "--models"]
    arguments += ["--scalar", "DateTime=datetime:datetime"]
    assert main(arguments) == 0
    common = ["--isolated", "--line-length=100"]
    lint = ["ruff", "check", *common, "--select=E,F,I,B,UP"]
    lint += ["--config", 'lint.isort.known-third-party = ["apiroute"]', str(out)]
    checked = subprocess.run(lint, capture_output=True, text=True, check=False)
    assert checked.returncode == 0, checked.stdout
    formatted = subprocess.run(
        ["ruff", "format", "--check", *common, str(out)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert formatted.returncode == 0, formatted.stdout
