"""What type checkers see for callers, checked with mypy (a dev dependency)."""

import re
import subprocess
import sys
from pathlib import Path

import pytest

from apiroute.codegen.openapi.openapi_reader import OpenApiReader
from apiroute.codegen.package_emitter import PackageEmitter

pytest.importorskip("mypy")
pytest.importorskip("pydantic")  # the generated typed layer's models

HERE = Path(__file__).parent
FIXTURES = HERE.parent / "codegen" / "fixtures"


def mypy(*paths: Path, cwd: Path) -> dict[str, list[tuple[int, str]]]:
    """mypy's errors, by file name: (line, error code)."""
    command = [sys.executable, "-m", "mypy", "--python-version", "3.10", "--show-error-codes"]
    command += [
        "--no-error-summary",
        "--hide-error-context",
        "--cache-dir",
        str(cwd / ".mypy_cache"),
    ]
    result = subprocess.run([*command, *map(str, paths)], cwd=cwd, capture_output=True, text=True)
    errors: dict[str, list[tuple[int, str]]] = {}
    for match in re.finditer(r"^(.+?):(\d+): error: .*\[([\w-]+)\]$", result.stdout, re.M):
        errors.setdefault(Path(match[1]).name, []).append((int(match[2]), match[3]))
    if result.returncode not in (0, 1):
        pytest.fail(f"mypy crashed:\n{result.stdout}{result.stderr}")
    return errors


def expected_errors(path: Path) -> list[tuple[int, str]]:
    lines = path.read_text().splitlines()
    return [
        (number, line.split("# E: ")[1]) for number, line in enumerate(lines, 1) if "# E: " in line
    ]


@pytest.fixture(scope="module")
def checked(tmp_path_factory) -> dict[str, list[tuple[int, str]]]:
    """One mypy run over the samples and a generated package used through its typed layer."""
    work = tmp_path_factory.mktemp("typing")
    definition = OpenApiReader(str(FIXTURES / "shop.yaml"), "ShopApi").read()
    PackageEmitter(definition, with_models=True).write(work / "shop")
    (work / "caller.py").write_text(
        "from typing import Any\n\n"
        "from typing_extensions import assert_type\n\n"
        "from shop import ShopApi\n"
        "from shop.pets.models.models import Pet\n\n"
        'api = ShopApi(token="t", api_key="k", partner="p")\n'
        "assert_type(api.pets.models.get_pet(1), Pet)\n"
        'assert_type(api.pets.models.list_pets(status="available"), list[Pet])\n'
        "assert_type(api.pets.get_pet(1), dict[str, Any])\n"
        "api.pets.get_pet('1')\n"
        "api.pets.models.list_pets()\n"
    )
    return mypy(
        HERE / "well_typed.py", HERE / "badly_typed.py", work / "caller.py", work / "shop", cwd=work
    )


def test_well_typed_code_passes(checked):
    assert checked.get("well_typed.py", []) == []


def test_wrong_calls_are_errors_on_exactly_the_marked_lines(checked):
    assert sorted(checked.get("badly_typed.py", [])) == expected_errors(HERE / "badly_typed.py")


def test_a_generated_package_is_typed_through_to_its_models(checked):
    # get_pet takes an int, and list_pets needs its required status; the rest type-checks
    assert checked.get("caller.py", []) == [(12, "arg-type"), (13, "call-arg")]


def test_a_generated_package_type_checks(checked):
    generated = {
        name: errors
        for name, errors in checked.items()
        if name not in ("well_typed.py", "badly_typed.py", "caller.py")
    }
    assert generated == {}
