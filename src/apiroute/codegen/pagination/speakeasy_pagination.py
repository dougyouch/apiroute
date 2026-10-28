import re
from typing import Any

from apiroute.codegen.pagination.strategy_call import StrategyCall

_JSON_PATH = re.compile(r"^\$(\.[A-Za-z_][\w-]*)*$")


def speakeasy_strategy(extension: Any) -> StrategyCall:
    """The strategy an x-speakeasy-pagination extension describes; a ValueError saying why
    when it's one apiroute doesn't map (another type, a JSONPath beyond dotted keys)."""
    if not isinstance(extension, dict):
        raise ValueError("expected an object")
    inputs = {i.get("type"): i for i in extension.get("inputs", []) if isinstance(i, dict)}
    outputs = extension.get("outputs") or {}
    items = {"items": _path(outputs["results"])} if "results" in outputs else {}
    kind, arguments = _strategy(extension.get("type"), inputs, outputs)
    return StrategyCall(kind, {**arguments, **items})


def _strategy(kind: Any, inputs: dict, outputs: dict) -> tuple[str, dict[str, Any]]:
    if kind == "offsetLimit":
        return _offset_limit(inputs, outputs)
    if kind == "cursor" and "cursor" in inputs and "nextCursor" in outputs:
        cursor = inputs["cursor"]
        arguments = {"param": cursor["name"], "token": _path(outputs["nextCursor"])}
        if cursor.get("in") == "requestBody":
            arguments["location"] = "body"
        return "cursor", arguments
    if kind == "url" and "nextUrl" in outputs:
        return "next_url", {"path": _path(outputs["nextUrl"])}
    raise ValueError(f"type {kind!r} with these inputs and outputs isn't supported")


def _offset_limit(inputs: dict, outputs: dict) -> tuple[str, dict[str, Any]]:
    limit = inputs.get("limit", {}).get("name")
    if "page" in inputs:
        arguments = {"param": inputs["page"]["name"]}
        if limit is not None:
            arguments["size"] = limit
        if "numPages" in outputs:
            arguments["total_pages"] = _path(outputs["numPages"])
        return "page", arguments
    if "offset" in inputs:
        arguments = {"param": inputs["offset"]["name"]}
        if limit is not None:
            arguments["limit"] = limit
        return "offset", arguments
    raise ValueError("offsetLimit needs an offset or page input")


def _path(json_path: Any) -> str:
    """$.data.items as data.items, and $ as the body ("")."""
    if not isinstance(json_path, str) or not _JSON_PATH.match(json_path):
        raise ValueError(f"the JSONPath {json_path!r} isn't a path of dotted keys")
    return json_path[2:]
