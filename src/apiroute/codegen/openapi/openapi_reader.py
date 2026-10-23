from typing import Any
from urllib.parse import urlsplit

from apiroute.codegen.api_definition import (
    ApiDefinition,
    AuthScheme,
    Group,
    Operation,
    Parameter,
    RequestBody,
)
from apiroute.codegen.openapi.ref_resolver import RefResolver
from apiroute.codegen.openapi.schema_mapper import SchemaMapper
from apiroute.codegen.openapi.spec_loader import SpecLoader
from apiroute.codegen.openapi.swagger2_converter import Swagger2Converter
from apiroute.codegen.plain_text import plain_text
from apiroute.codegen.python_names import pascal_case, snake_case, unique
from apiroute.codegen.type_ref import ANY

_METHODS = ("get", "put", "post", "delete", "options", "head", "patch", "trace")
_FORMS = {"application/x-www-form-urlencoded": "form", "multipart/form-data": "multipart"}


class OpenApiReader:
    """Reads an OpenAPI 3.x or Swagger 2.0 spec into an ApiDefinition: one group per tag
    (an operation's first tag), untagged operations at the root."""

    def __init__(self, location: str, client_name: str, loader: SpecLoader | None = None):
        self._location = location
        self._client_name = client_name
        self._loader = loader or SpecLoader()

    def read(self) -> ApiDefinition:
        document = self._loader.load(self._location)
        if str(document.get("swagger", "")).startswith("2"):
            document = Swagger2Converter().convert(document)
        self._resolver = RefResolver(document, self._location, self._loader)
        definition = ApiDefinition(
            client_name=self._client_name,
            base_url=_base_url(document, self._location),
            title=plain_text(document.get("info", {}).get("title", "")),
            description=plain_text(document.get("info", {}).get("description", "")),
            source=self._source_name(),
            root=Group("", self._client_name),
        )
        self._mapper = SchemaMapper(self._resolver, definition.models)
        self._groups: dict[str, Group] = {}
        self._group_names: set[str] = set()
        self._tag_descriptions = {  # tag -> plain-text description
            t["name"]: plain_text(t.get("description", "")) for t in document.get("tags", [])
        }
        for path, item in document.get("paths", {}).items():
            self._read_path(definition, path, self._resolver.deref(item))
        definition.groups = list(self._groups.values())
        for name in document.get("components", {}).get("schemas", {}):
            self._mapper.register_named(name, f"#/components/schemas/{_escape(name)}")
        definition.auth = _auth(document.get("components", {}).get("securitySchemes", {}))
        return definition

    def _source_name(self) -> str:
        return self._location.rsplit("/", 1)[-1]

    def _read_path(self, definition: ApiDefinition, path: str, item: dict) -> None:
        shared = item.get("parameters", [])
        for method in _METHODS:
            if method in item:
                operation = self._resolver.deref(item[method])
                group = self._group(definition, operation)
                group.operations.append(self._operation(group, method, path, operation, shared))

    def _group(self, definition: ApiDefinition, operation: dict) -> Group:
        tags = operation.get("tags") or []
        if not tags:
            return definition.root
        tag = tags[0]
        if tag not in self._groups:
            name = unique(snake_case(tag), self._group_names)
            self._groups[tag] = Group(
                name, f"{pascal_case(tag)}Section", self._tag_descriptions.get(tag, "")
            )
        return self._groups[tag]

    def _operation(
        self, group: Group, method: str, path: str, operation: dict, shared: list
    ) -> Operation:
        taken = {o.name for o in group.operations}
        name = unique(self._operation_name(group, method, path, operation), taken)
        hint = pascal_case(name if not group.name else f"{group.name}_{name}")
        parameters, path = self._parameters([*shared, *operation.get("parameters", [])], path, hint)
        result = Operation(
            name=name,
            method=method.upper(),
            path=path,
            summary=plain_text(operation.get("summary") or operation.get("description", "")),
            parameters=parameters,
            body=self._body(operation.get("requestBody"), hint),
            deprecated=bool(operation.get("deprecated")),
            operation_id=operation.get("operationId", ""),
        )
        self._response(result, operation.get("responses", {}), hint)
        return result

    def _operation_name(self, group: Group, method: str, path: str, operation: dict) -> str:
        operation_id = operation.get("operationId")
        if not operation_id:
            return snake_case(f"{method} {path.replace('{', ' by ').replace('}', '')}")
        name = snake_case(operation_id)
        prefix = f"{group.name}_"
        if group.name and name.startswith(prefix) and len(name) > len(prefix):
            name = name[len(prefix) :]  # repos/get in the repos section -> get
        return name

    def _parameters(self, raw: list, path: str, hint: str) -> tuple[list[Parameter], str]:
        by_key: dict[tuple[str, str], dict] = {}
        for parameter in raw:
            parameter = self._resolver.deref(parameter)
            if parameter.get("in") in ("path", "query", "header"):
                by_key[(parameter["in"], parameter["name"])] = parameter
        taken = {"body", "self"}
        parameters = []
        for (location, wire_name), parameter in by_key.items():
            name = unique(snake_case(wire_name), taken, frozenset())
            if location == "path":
                path = path.replace(f"{{{wire_name}}}", f"{{{name}}}")
            schema = parameter.get("schema", {})
            parameters.append(
                Parameter(
                    name=name,
                    wire_name=wire_name,
                    location=location,
                    type=self._mapper.map(schema, f"{hint}{pascal_case(wire_name)}"),
                    required=location == "path" or bool(parameter.get("required")),
                    description=parameter.get("description", ""),
                )
            )
        return parameters, path

    def _body(self, request_body: Any, hint: str) -> RequestBody | None:
        if not request_body:
            return None
        request_body = self._resolver.deref(request_body)
        content = request_body.get("content", {})
        media = _pick_media(content)
        if media is None:
            return None
        schema = content[media].get("schema", {})
        return RequestBody(
            type=self._mapper.map(schema, f"{hint}Request"),
            required=bool(request_body.get("required")),
            body_format=_FORMS.get(media, "json"),
            plain=self._mapper.plain(schema),
        )

    def _response(self, operation: Operation, responses: dict, hint: str) -> None:
        status, response = _success(responses)
        if response is None:
            return
        content = self._resolver.deref(response).get("content", {})
        media = _pick_media(content)
        if media is None:
            operation.response_plain = "None" if status == "204" or not content else "Any"
            if content:
                operation.returns = "text" if next(iter(content)).startswith("text/") else "bytes"
            return
        if media in _FORMS or not ("json" in media or media == "*/*"):
            operation.returns = "text" if media.startswith("text/") else "bytes"
            return
        schema = content[media].get("schema", {})
        operation.response = self._mapper.map(schema, f"{hint}Response")
        operation.response_plain = self._mapper.plain(schema)
        if operation.response == ANY:
            operation.response = None


def _pick_media(content: dict) -> str | None:
    """JSON first, then forms; None for bodies the generator treats as raw."""
    for media in content:
        if media == "application/json" or media.endswith("+json"):
            return media
    for media in content:
        if media in _FORMS or "json" in media or media == "*/*":
            return media
    return None


def _success(responses: dict) -> tuple[str | None, dict | None]:
    for status in sorted(responses, key=str):
        if str(status).startswith("2"):
            return str(status), responses[status]
    if "default" in responses:
        return "default", responses["default"]
    return None, None


def _base_url(document: dict, location: str) -> str | None:
    servers = document.get("servers") or []
    if not servers:
        return None
    server = servers[0]
    url = server.get("url", "")
    for name, variable in server.get("variables", {}).items():
        url = url.replace(f"{{{name}}}", str(variable.get("default", "")))
    if urlsplit(url).scheme in ("http", "https"):
        return url.rstrip("/")
    if urlsplit(location).scheme in ("http", "https"):
        origin = "{0.scheme}://{0.netloc}".format(urlsplit(location))
        return f"{origin}{url}".rstrip("/")
    return None


def _auth(schemes: dict) -> list[AuthScheme]:
    result: list[AuthScheme] = []
    taken: set[str] = set()
    for name, scheme in schemes.items():
        kind = scheme.get("type")
        if kind == "apiKey" and scheme.get("in") in ("header", "query"):
            attribute = unique(snake_case(name), taken, frozenset())
            result.append(AuthScheme(attribute, scheme["in"], scheme["name"]))
        elif kind == "http" and scheme.get("scheme", "").lower() == "basic":
            result.append(
                AuthScheme(
                    unique("basic_auth", taken, frozenset()),
                    "header",
                    "Authorization",
                    "basic",
                    "user:password",
                )
            )
        elif kind in ("http", "oauth2", "openIdConnect") and "token" not in taken:
            result.append(
                AuthScheme(unique("token", taken, frozenset()), "header", "Authorization", "bearer")
            )
    return result


def _escape(name: str) -> str:
    return name.replace("~", "~0").replace("/", "~1")
