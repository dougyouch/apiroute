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
