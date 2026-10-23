import copy
from typing import Any

_FORM_TYPES = ("application/x-www-form-urlencoded", "multipart/form-data")


class Swagger2Converter:
    """Rewrites a Swagger 2.0 document into the OpenAPI 3.0 shape the reader understands:
    host/basePath/schemes become servers, definitions become components.schemas, body and
    formData parameters become requestBody, and response schemas move under content."""

    def convert(self, swagger: dict[str, Any]) -> dict[str, Any]:
        document = copy.deepcopy(swagger)
        _rewrite_refs(document)
        consumes = document.get("consumes") or ["application/json"]
        produces = document.get("produces") or ["application/json"]
        return {
            "openapi": "3.0.3",
            "info": document.get("info", {}),
            "servers": _servers(document),
            "tags": document.get("tags", []),
            "paths": {
                path: self._path_item(item, consumes, produces)
                for path, item in document.get("paths", {}).items()
            },
            "components": {
                "schemas": document.get("definitions", {}),
                "securitySchemes": _security(document.get("securityDefinitions", {})),
            },
        }

    def _path_item(self, item: dict, consumes: list[str], produces: list[str]) -> dict:
        converted = {}
        for key, value in item.items():
            if key == "parameters":
                converted[key] = [p for p in value if p.get("in") not in ("body", "formData")]
            elif isinstance(value, dict):
                converted[key] = self._operation(value, consumes, produces, item)
            else:
                converted[key] = value
        return converted

    def _operation(self, operation: dict, consumes: list, produces: list, item: dict) -> dict:
        converted = {k: v for k, v in operation.items() if k not in ("parameters", "responses")}
        parameters = [*item.get("parameters", []), *operation.get("parameters", [])]
        converted["parameters"] = [
            _parameter(p)
            for p in operation.get("parameters", [])
            if p.get("in") not in ("body", "formData")
        ]
        body = _request_body(parameters, operation.get("consumes") or consumes)
        if body:
            converted["requestBody"] = body
        media = (operation.get("produces") or produces)[0]
        converted["responses"] = {
            status: _response(response, media)
            for status, response in operation.get("responses", {}).items()
        }
        return converted


def _servers(document: dict) -> list[dict]:
    host = document.get("host")
    if not host:
        return [{"url": document.get("basePath", "/")}]
    scheme = "https" if "https" in document.get("schemes", ["https"]) else "http"
    return [{"url": f"{scheme}://{host}{document.get('basePath', '')}"}]


def _parameter(parameter: dict) -> dict:
    schema_keys = ("type", "format", "items", "enum", "default", "minimum", "maximum")
    converted = {k: v for k, v in parameter.items() if k not in schema_keys}
    converted["schema"] = {k: v for k, v in parameter.items() if k in schema_keys}
    return converted


def _request_body(parameters: list[dict], consumes: list[str]) -> dict | None:
    body = next((p for p in parameters if p.get("in") == "body"), None)
    if body is not None:
        media = next((c for c in consumes if "json" in c), consumes[0])
        return {
            "required": body.get("required", False),
            "content": {media: {"schema": body.get("schema", {})}},
            "description": body.get("description", ""),
        }
    form = [p for p in parameters if p.get("in") == "formData"]
    if not form:
        return None
    files = any(p.get("type") == "file" for p in form)
    media = (
        "multipart/form-data"
        if files
        else next((c for c in consumes if c in _FORM_TYPES), "application/x-www-form-urlencoded")
    )
    properties = {
        p["name"]: {"type": "string", "format": "binary"}
        if p.get("type") == "file"
        else _parameter(p)["schema"]
        for p in form
    }
    required = [p["name"] for p in form if p.get("required")]
    schema = {"type": "object", "properties": properties, "required": required}
    return {"required": bool(required), "content": {media: {"schema": schema}}}


def _response(response: dict, media: str) -> dict:
    converted = {k: v for k, v in response.items() if k != "schema"}
    if "schema" in response:
        converted["content"] = {media: {"schema": response["schema"]}}
    return converted


def _security(definitions: dict) -> dict:
    schemes = {}
    for name, definition in definitions.items():
        kind = definition.get("type")
        if kind == "basic":
            schemes[name] = {"type": "http", "scheme": "basic"}
        elif kind == "oauth2":
            schemes[name] = {"type": "oauth2"}
        else:
            schemes[name] = definition
    return schemes


def _rewrite_refs(value: Any) -> None:
    if isinstance(value, dict):
        ref = value.get("$ref")
        if isinstance(ref, str) and ref.startswith("#/definitions/"):
            value["$ref"] = ref.replace("#/definitions/", "#/components/schemas/", 1)
        for item in value.values():
            _rewrite_refs(item)
    elif isinstance(value, list):
        for item in value:
            _rewrite_refs(item)
