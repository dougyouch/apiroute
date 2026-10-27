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
    return _load_file(str(_resolve(Path(source), holder)))


@functools.cache
def _load_file(path: str) -> Any:
    from graphql import build_client_schema, build_schema

    try:
        text = Path(path).read_text(encoding="utf-8")
    except OSError as error:
        raise ValueError(f"can't read graphql_schema {path}: {error.strerror}") from error
    try:
        if path.endswith(".json"):
            return build_client_schema(_introspection(json.loads(text)))
        return build_schema(text)
    except Exception as error:
        raise ValueError(f"graphql_schema {path} isn't a valid schema: {error}") from error


def _introspection(data: Any) -> Any:
    """An introspection result, inside its {"data": ...} response envelope or not."""
    if isinstance(data, dict) and isinstance(data.get("data"), dict):
        return data["data"]
    return data


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
