import argparse
import sys
from pathlib import Path

import httpx

from apiroute.codegen.package_emitter import PackageEmitter
from apiroute.codegen.python_names import pascal_case
from apiroute.codegen.source_formatter import SourceFormatter


def main(argv: list[str] | None = None) -> int:
    arguments = _parser().parse_args(argv)
    out_dir = Path(arguments.output)
    client_name = arguments.client_name or f"{pascal_case(out_dir.name)}Api"
    try:
        definition = _reader(arguments.format, arguments.spec, client_name).read()
        definition.base_class = arguments.base_class
        written = PackageEmitter(definition, with_models=arguments.models).write(out_dir)
        formatted = not arguments.no_format and SourceFormatter().format(written)
    except (OSError, ValueError, KeyError, RuntimeError, httpx.HTTPError) as error:
        # The CLI is the boundary: report the reason, not a traceback
        print(f"apiroute: {type(error).__name__}: {error}", file=sys.stderr)
        return 1
    operations = len(definition.root.operations) + sum(len(g.operations) for g in definition.groups)
    models = f", {len(definition.models)} models" if arguments.models else ""
    note = " (formatted with ruff)" if formatted else ""
    print(f"Wrote {len(written)} files to {out_dir}{note}: {operations} operations{models}")
    return 0


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="apiroute", description="apiroute client tools")
    commands = parser.add_subparsers(dest="command", required=True)
    generate = commands.add_parser(
        "generate",
        help="generate a client package from an API description",
        description="Generate a client package: dict routes always, pydantic models with --models.",
    )
    generate.add_argument("format", choices=["openapi", "wsdl"], help="openapi covers Swagger 2.0")
    generate.add_argument("spec", help="a file path or http(s) URL")
    generate.add_argument("-o", "--output", required=True, help="the package directory to write")
    generate.add_argument("--client-name", help="the root client class (default: <Output>Api)")
    generate.add_argument(
        "--models",
        action="store_true",
        help="also generate the typed .models layer (pydantic request and response models)",
    )
    generate.add_argument(
        "--base-class",
        metavar="MODULE:CLASS",
        help="a hand-written Client subclass for the root client to extend, which owns auth "
        "(e.g. myapi.auth:MyAuth); the spec's security schemes are then not generated",
    )
    generate.add_argument(
        "--no-format",
        action="store_true",
        help="don't run `ruff format` on the output, even when ruff is installed",
    )
    return parser


def _reader(format_name: str, spec: str, client_name: str):
    if format_name == "openapi":
        from apiroute.codegen.openapi.openapi_reader import OpenApiReader

        return OpenApiReader(spec, client_name)
    from apiroute.codegen.wsdl.wsdl_reader import WsdlReader

    return WsdlReader(spec, client_name)


if __name__ == "__main__":
    sys.exit(main())
