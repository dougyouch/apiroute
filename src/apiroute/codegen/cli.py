import argparse
import json
import sys
from pathlib import Path

import httpx

from apiroute.base_url_validator import validate_base_url
from apiroute.codegen.nullable_fields import NullableFields
from apiroute.codegen.operation_names import OperationNames
from apiroute.codegen.package_emitter import PackageEmitter
from apiroute.codegen.python_names import pascal_case
from apiroute.codegen.source_formatter import SourceFormatter


def main(argv: list[str] | None = None) -> int:
    arguments = _parser().parse_args(argv)
    if arguments.command == "fetch-schema":
        return _fetch_schema(arguments)
    return _generate(arguments)


def _generate(arguments: argparse.Namespace) -> int:
    out_dir = Path(arguments.output)
    client_name = arguments.client_name or f"{pascal_case(out_dir.name)}Api"
    try:
        definition = _reader(arguments, client_name).read()
        if arguments.operation_names:
            OperationNames.load(arguments.operation_names).apply(definition)
        for warning in definition.warnings:
            print(f"apiroute: warning: {warning}", file=sys.stderr)
        definition.base_class = arguments.base_class
        if arguments.nullable_fields:
            NullableFields().apply(definition)
        if arguments.base_url is not None:
            validate_base_url(arguments.base_url)
            definition.base_url = arguments.base_url.rstrip("/")
        written = PackageEmitter(definition, with_models=arguments.models).write(out_dir)
        first_party = (
            [arguments.base_class.split(":")[0].split(".")[0]] if arguments.base_class else []
        )
        formatted = not arguments.no_format and SourceFormatter().format(
            written, first_party=first_party
        )
    except (OSError, ValueError, KeyError, RuntimeError, httpx.HTTPError) as error:
        # The CLI is the boundary: report the reason, not a traceback
        print(f"apiroute: {type(error).__name__}: {error}", file=sys.stderr)
        return 1
    operations = len(definition.root.operations) + sum(len(g.operations) for g in definition.groups)
    models = f", {len(definition.models)} models" if arguments.models else ""
    note = " (formatted with ruff)" if formatted else ""
    print(f"Wrote {len(written)} files to {out_dir}{note}: {operations} operations{models}")
    return 0


def _fetch_schema(arguments: argparse.Namespace) -> int:
    from apiroute.codegen.graphql.schema_fetcher import SchemaFetcher

    out = Path(arguments.output)
    try:
        _require_graphql_core()
        data = SchemaFetcher().introspect(arguments.endpoint, _headers(arguments.header))
        out.write_text(_schema_text(data, as_json=out.suffix == ".json"))
    except (OSError, ValueError, RuntimeError, httpx.HTTPError) as error:
        print(f"apiroute: {type(error).__name__}: {error}", file=sys.stderr)
        return 1
    print(f"Wrote the schema of {arguments.endpoint} to {out}")
    return 0


def _schema_text(data: dict, as_json: bool) -> str:
    """The introspection result as indented JSON, or the schema it describes as SDL."""
    if as_json:
        return json.dumps({"data": data}, indent=2, ensure_ascii=False) + "\n"
    from graphql import print_schema

    from apiroute.graphql.graphql_schema_loader import schema_from_introspection

    return print_schema(schema_from_introspection(data)) + "\n"


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="apiroute", description="apiroute client tools")
    commands = parser.add_subparsers(dest="command", required=True)
    generate = commands.add_parser(
        "generate",
        help="generate a client package from an API description",
        description="Generate a client package: dict routes always, pydantic models with --models.",
    )
    generate.add_argument(
        "format", choices=["openapi", "wsdl", "graphql"], help="openapi covers Swagger 2.0"
    )
    generate.add_argument(
        "spec",
        help="a file path or http(s) URL; for graphql, the schema: an SDL or .json introspection "
        "file, or an endpoint to introspect",
    )
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
        "--base-url",
        metavar="URL",
        help="the root client's base_url, overriding the spec's servers; needed for a spec read "
        "from a file whose server URL is relative (e.g. /api/v2)",
    )
    generate.add_argument(
        "--operation-names",
        metavar="FILE",
        help="a JSON object of operation IDs to dotted names (customers.create, "
        "issuing.cards.list): the last part is the method, the parts before it nested "
        "sections; for a spec whose tags and operationIds make poor names",
    )
    generate.add_argument(
        "--nullable-fields",
        action="store_true",
        help="type every model field as accepting null, for a spec that leaves out nullable "
        "where the API does return null",
    )
    generate.add_argument(
        "--no-format",
        action="store_true",
        help="don't run `ruff format` on the output, even when ruff is installed",
    )
    graphql = generate.add_argument_group("graphql")
    graphql.add_argument(
        "--operations",
        metavar="DIR",
        help="the .graphql operation files; each subdirectory becomes a section",
    )
    graphql.add_argument(
        "--endpoint",
        metavar="URL",
        help="the GraphQL endpoint (e.g. https://api.github.com/graphql): the root client's "
        "base_url and the routes' path",
    )
    graphql.add_argument(
        "--scalar",
        action="append",
        default=[],
        metavar="NAME=MODULE:TYPE",
        help="the Python type of a custom scalar in the models, e.g. DateTime=datetime:datetime "
        "(default: Any); repeatable",
    )
    graphql.add_argument(
        "--persisted-queries",
        action="store_true",
        help="send every operation as an automatic persisted query (its hash, registering "
        "the document on a miss)",
    )
    _add_header_option(graphql, "for introspecting a schema endpoint")
    fetch = commands.add_parser(
        "fetch-schema",
        help="save a GraphQL endpoint's schema by introspection",
        description="Introspect a GraphQL endpoint and write its schema: SDL, or the "
        "introspection JSON when the output ends in .json.",
    )
    fetch.add_argument("endpoint", help="the GraphQL endpoint URL")
    fetch.add_argument("-o", "--output", required=True, help="the file to write")
    _add_header_option(fetch, "sent with the introspection query")
    return parser


def _add_header_option(group, purpose: str) -> None:
    group.add_argument(
        "-H",
        "--header",
        action="append",
        default=[],
        metavar="'NAME: VALUE'",
        help=f"a request header {purpose}, e.g. 'Authorization: Bearer $TOKEN'; repeatable",
    )


def _reader(arguments: argparse.Namespace, client_name: str):
    if arguments.format == "graphql":
        return _graphql_reader(arguments, client_name)
    if arguments.operations is not None:
        raise ValueError("--operations only applies to graphql")
    if arguments.persisted_queries:
        raise ValueError("--persisted-queries only applies to graphql")
    if arguments.format == "openapi":
        from apiroute.codegen.openapi.openapi_reader import OpenApiReader

        return OpenApiReader(arguments.spec, client_name)
    from apiroute.codegen.wsdl.wsdl_reader import WsdlReader

    return WsdlReader(arguments.spec, client_name)


def _graphql_reader(arguments: argparse.Namespace, client_name: str):
    from apiroute.codegen.graphql.graphql_reader import GraphQLReader

    if arguments.operations is None:
        raise ValueError("generate graphql needs --operations DIR")
    if arguments.base_url is not None:
        raise ValueError("generate graphql takes --endpoint, not --base-url")
    return GraphQLReader(
        arguments.spec,
        arguments.operations,
        client_name,
        endpoint=arguments.endpoint,
        headers=_headers(arguments.header),
        scalars=_scalars(arguments.scalar),
        persisted=arguments.persisted_queries,
    )


def _headers(values: list[str]) -> dict[str, str]:
    headers = {}
    for value in values:
        name, separator, content = value.partition(":")
        if not separator or not name.strip():
            raise ValueError(f"--header takes 'Name: value', not {value!r}")
        headers[name.strip()] = content.strip()
    return headers


def _scalars(values: list[str]) -> dict[str, tuple[str, str]]:
    scalars = {}
    for value in values:
        name, _, target = value.partition("=")
        module, _, attribute = target.partition(":")
        if not (name and module and attribute.isidentifier()):
            raise ValueError(f"--scalar takes NAME=MODULE:TYPE, not {value!r}")
        scalars[name] = (module, attribute)
    return scalars


def _require_graphql_core() -> None:
    try:
        import graphql  # noqa: F401
    except ImportError as error:
        raise RuntimeError(
            "fetch-schema needs graphql-core: pip install apiroute[codegen]"
        ) from error


if __name__ == "__main__":
    sys.exit(main())
