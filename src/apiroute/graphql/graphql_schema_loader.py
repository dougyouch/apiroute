import functools
import json
import os
import sys
from pathlib import Path
from typing import Any


def load_schema(holder: type) -> Any:
    """The graphql.GraphQLSchema that holder's graphql_schema names: a schema object as is, or
    a file, resolved against the module of the class declaring the attribute. A .json file is
    an introspection result, anything else SDL. Each file is built once per process."""
    graphql = _graphql_core()
    source = holder.graphql_schema
    if isinstance(source, graphql.GraphQLSchema):
        return source
    if not isinstance(source, (str, os.PathLike)):
        raise TypeError("graphql_schema must be a file path or a graphql.GraphQLSchema")
    return load_schema_file(str(_resolve(Path(source), holder)))


@functools.cache
def load_schema_file(path: str) -> Any:
    """The schema in an SDL file or, for a .json file, an introspection result; built once
    per process for each path."""
    from graphql import build_schema

    try:
        text = Path(path).read_text(encoding="utf-8")
    except OSError as error:
        raise ValueError(f"can't read GraphQL schema {path}: {error.strerror}") from error
    try:
        if path.endswith(".json"):
            return schema_from_introspection(json.loads(text))
        return build_schema(text, assume_valid=True)
    except Exception as error:
        raise ValueError(f"GraphQL schema {path} isn't a valid schema: {error}") from error


def schema_from_introspection(data: Any) -> Any:
    """The schema an introspection result describes, inside its {"data": ...} response
    envelope or not. Directive locations this graphql-core doesn't know are dropped: servers
    on a newer spec list some (@deprecated on DIRECTIVE_DEFINITION) that graphql-core 3.2
    refuses, and they don't affect validating operations.

    Schemas are assumed valid: they describe what a server answers, and real ones break rules
    newer graphql-core enforces (GitHub's deprecates fields its interfaces don't), which would
    otherwise stop every operation from being validated against them."""
    from graphql import DirectiveLocation, build_client_schema

    if isinstance(data, dict) and isinstance(data.get("data"), dict):
        data = data["data"]
    known = {location.name for location in DirectiveLocation}
    for directive in data.get("__schema", {}).get("directives") or []:
        directive["locations"] = [
            location for location in directive.get("locations", []) if location in known
        ]
    return build_client_schema(data, assume_valid=True)


def _resolve(path: Path, holder: type) -> Path:
    if path.is_absolute():
        return path
    return (_module_dir(_declaring_class(holder)) / path).resolve()


def _declaring_class(holder: type) -> type:
    return next(cls for cls in holder.__mro__ if "graphql_schema" in vars(cls))


def _module_dir(cls: type) -> Path:
    """The directory of the module defining cls, or the current one for a module without a
    file (a REPL, python -c)."""
    file = getattr(sys.modules.get(cls.__module__), "__file__", None)
    return Path(file).parent if file else Path.cwd()


def _graphql_core() -> Any:
    try:
        import graphql
    except ImportError as error:
        raise ValueError(
            "graphql_schema needs graphql-core: pip install apiroute[graphql]"
        ) from error
    return graphql
