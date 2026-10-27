import re

from apiroute.codegen.alias_inliner import AliasInliner
from apiroute.codegen.api_definition import ApiDefinition, AuthScheme, Group, Operation, Parameter
from apiroute.codegen.generated_header import generated_header
from apiroute.codegen.import_order import import_names
from apiroute.codegen.models_client_emitter import models_class_name
from apiroute.codegen.python_literals import py_str, py_value
from apiroute.codegen.source_writer import SourceWriter
from apiroute.graphql.snake_case import snake_case as graphql_snake_case


class DictClientEmitter:
    """Writes a level's client.py: the root Client or a tag's Section, whose routes take and
    return plain dicts. Routes compile lazily, and sub-sections and the .models view are
    lazy attributes, so importing this module loads nothing else."""

    def __init__(self, definition: ApiDefinition, group: Group, with_models: bool, version: str):
        self._definition = definition
        self._group = group
        self._is_root = group is definition.root
        self._with_models = with_models
        self._version = version
        self._inliner = AliasInliner(definition)
        self._base_class = _split_base_class(definition.base_class) if self._is_root else None

    def source(self) -> str:
        out = SourceWriter()
        out.line(generated_header(self._version, self._definition.source))
        if self._group.operations:
            # route bodies are ... by design: the decorator replaces them
            out.line('# mypy: disable-error-code="empty-body"')
        if any(operation.graphql for operation in self._group.operations):
            out.line("# ruff: noqa: E501  (GraphQL documents keep their own line lengths)")
        out.docstring(self._module_doc())
        out.line()
        # Annotations stay strings: a route named list or dict must not shadow the builtins
        # that later annotations in the class body use (Python 3.10-3.13 evaluate them early)
        out.line("from __future__ import annotations")
        out.line()
        self._imports(out)
        out.lines("", "")
        self._class(out)
        return out.text()

    def _module_doc(self) -> str:
        if self._is_root:
            return self._definition.title or self._definition.client_name
        return f"The {self._group.name} endpoints."

    def _imports(self, out: SourceWriter) -> None:
        """Only what the class uses, so generated files pass a linter untouched."""
        body = self._body_text()
        standard = []
        if self._is_root and any(scheme.style == "basic" for scheme in self._definition.auth):
            standard.append("import base64")
        if _mentions(body, "Iterator"):
            standard.append("from collections.abc import Iterator")
        typing_names = [n for n in ("Annotated", "Any", "Literal") if _mentions(body, n)]
        if self._lazy_entries():
            typing_names.append("TYPE_CHECKING")
        if typing_names:
            standard.append(f"from typing import {import_names(typing_names)}")
        if standard:
            out.lines(*standard, "")
        names = [n for n in ("Header", "Query", "graphql_route", "route") if _mentions(body, n)]
        if re.search(r"\blazy\(", body):  # not the word in compile_routes = "lazy"
            names.append("lazy")
        if not self._is_root:
            names.append("Section")
        elif self._base_class is None:
            names.append("Client")
        out.line(f"from apiroute import {import_names(names)}")
        soap = [n for n in ("SoapBody", "SoapDecoder") if _mentions(body, n)]
        if soap:
            out.line(f"from apiroute.soap import {import_names(soap)}")
        if self._base_class is not None:
            # the user's own code: a first-party block of its own, as isort orders it
            module, name = self._base_class
            out.lines("", f"from {module} import {name}")
        self._type_checking_imports(out)

    def _type_checking_imports(self, out: SourceWriter) -> None:
        """The classes the lazy attributes load, for type checkers only: importing them here
        at run time would load every section and model when the client is imported."""
        entries = self._lazy_entries()
        if not entries:
            return
        out.lines("", "if TYPE_CHECKING:")
        with out.indented():
            for _, module, class_name in sorted(entries, key=lambda entry: entry[1]):
                out.line(f"from {module} import {class_name}")

    def _body_text(self) -> str:
        out = SourceWriter()
        self._class(out)
        return out.text()

    def _class(self, out: SourceWriter) -> None:
        base = "Client" if self._is_root else "Section"
        if self._base_class is not None:
            base = self._base_class[1]
        out.line(f"class {self._group.class_name}({base}):")
        with out.indented():
            # A section without its own (tag) description gets the short module docstring, not
            # the whole API's description repeated in every section
            fallback = self._definition.description if self._is_root else None
            doc = self._group.description or fallback
            out.docstring(doc or self._module_doc())
            out.line()
            self._settings(out)
            self._lazy_attributes(out)
            if self._is_root and self._definition.auth and self._base_class is None:
                self._init(out)
            for operation in self._group.operations:
                out.line()
                self._route(out, operation)

    def _settings(self, out: SourceWriter) -> None:
        if self._is_root and self._definition.base_url:
            out.line(f"base_url = {py_str(self._definition.base_url)}")
        out.line('compile_routes = "lazy"')
        if not self._is_root:
            # the client's auth, and its retry and timeout policy
            out.line('inherit = ("headers", "query_params", "retries", "timeout")')
        if self._is_root and self._base_class is None:
            self._auth_settings(out)

    def _auth_settings(self, out: SourceWriter) -> None:
        for location, attribute in (("header", "headers"), ("query", "query_params")):
            schemes = [s for s in self._definition.auth if s.location == location]
            if not schemes:
                continue
            out.line(f"{attribute} = {{")
            with out.indented():
                for scheme in schemes:
                    out.line(f"{py_str(scheme.wire_name)}: {_credential(scheme)},")
            out.line("}")

    def _lazy_entries(self) -> list[tuple[str, str, str]]:
        """(attribute, module, class) for each section (on the root) and the .models view."""
        entries = []
        if self._is_root:
            entries += [
                (group.name, f".{group.name}.client", group.class_name)
                for group in self._definition.groups
            ]
        if self._with_models:
            entries.append(("models", ".models.client", models_class_name(self._group)))
        return entries

    def _lazy_attributes(self, out: SourceWriter) -> None:
        """Annotated with their classes, so type checkers see client.pets as a PetsSection."""
        entries = self._lazy_entries()
        if entries:
            out.line()
        for name, module, class_name in entries:
            out.line(f"{name}: {class_name} = lazy({py_str(module)}, {py_str(class_name)})")

    def _init(self, out: SourceWriter) -> None:
        out.line()
        arguments = ", ".join(f"{s.attribute}: str | None = None" for s in self._definition.auth)
        out.line(f"def __init__(self, *, {arguments}, **kwargs: Any):")
        with out.indented():
            out.line("super().__init__(**kwargs)")
            for scheme in self._definition.auth:
                out.line(f"self.{scheme.attribute} = {scheme.attribute}")

    def _route(self, out: SourceWriter, operation: Operation) -> None:
        if operation.graphql is not None:
            _graphql_decorator(out, operation)
        else:
            out.line(f"@route({', '.join(_route_arguments(operation))})")
        out.line(f"def {operation.name}(")
        with out.indented():
            out.line("self,")
            for parameter in _ordered(operation, self._inliner):
                out.line(f"{parameter},")
        out.line(f") -> {_return_type(operation)}:")
        with out.indented():
            out.docstring(_doc(operation))
            # after a docstring too: pyright accepts a body ending in ... as a stub, and
            # mypy's empty-body check is off in generated files
            out.line("...")


def _mentions(text: str, name: str) -> bool:
    return re.search(rf"\b{name}\b", text) is not None


def _route_arguments(operation: Operation) -> list[str]:
    arguments = [py_str(operation.method), py_str(operation.path)]
    if operation.operation_id and operation.operation_id != operation.name:
        arguments.append(f"operation={py_str(operation.operation_id)}")
    if operation.returns != "json":
        arguments.append(f"returns={py_str(operation.returns)}")
    if operation.soap is not None:
        arguments += _soap_arguments(operation)
    elif operation.body is not None and operation.body.body_format != "json":
        arguments.append(f"body_format={py_str(operation.body.body_format)}")
    if operation.headers:
        arguments.append(f"headers={py_value(operation.headers)}")
    return arguments


def _graphql_decorator(out: SourceWriter, operation: Operation) -> None:
    """@graphql_route with the document as written to the wire; path= and variables= only
    when the defaults (/graphql, variables matched by name or snake_case) don't do."""
    spec = operation.graphql
    out.line("@graphql_route(")
    with out.indented():
        out.line(f"{_document_literal(spec.document)},")
        if spec.path != "/graphql":
            out.line(f"path={py_str(spec.path)},")
        if spec.paginate is not None:
            out.line(f"paginate={py_str(spec.paginate)},")
        if spec.persisted:
            out.line("persisted=True,")
        renamed = {
            p.wire_name: p.name
            for p in operation.parameters
            if p.name not in (p.wire_name, graphql_snake_case(p.wire_name))
        }
        if renamed:
            out.line(f"variables={py_value(renamed)},")
    out.line(")")


def _document_literal(document: str) -> str:
    """A triple-quoted string, readable in the generated file (the backslash after the opening
    quotes continues the line, so the document doesn't start with a newline), unless the
    document holds what that can't: block strings, backslashes."""
    if '"""' in document or "\\" in document or document.endswith('"'):
        return py_str(document)
    return f'"""\\\n{document}"""'


def _soap_arguments(operation: Operation) -> list[str]:
    """A SOAP fault comes back as HTTP 500; accepting it lets the decoder raise SoapFault."""
    soap = operation.soap
    body = [py_str(soap.element), py_str(soap.namespace), py_str(soap.version)]
    if not soap.qualified:
        body.append("qualified=False")
    if soap.version == "1.2" and soap.action:
        body.append(f"action={py_str(soap.action)}")
    if operation.operation_id:
        body.append(f"operation={py_str(operation.operation_id)}")
    decoder = f"SoapDecoder({py_str(soap.response_namespace)}, {py_str(soap.version)})"
    return [f"body_format=SoapBody({', '.join(body)})", f"decoder={decoder}", "expected=(200, 500)"]


def _ordered(operation: Operation, inliner: AliasInliner) -> list[str]:
    """Path parameters stay positional; everything else is keyword-only."""
    path = [p for p in operation.parameters if p.location == "path"]
    rest = [p for p in operation.parameters if p.location != "path"]
    parameters = [f"{p.name}: {inliner.plain(p.type)}" for p in path]
    keyword = [_keyword_parameter(p, inliner) for p in sorted(rest, key=lambda p: not p.required)]
    if operation.body is not None:
        body = f"body: {operation.body.plain}"
        keyword.insert(
            0 if operation.body.required else len(keyword),
            body if operation.body.required else f"{body} | None = None",
        )
    return parameters + (["*", *keyword] if keyword else [])


def _keyword_parameter(parameter: Parameter, inliner: AliasInliner) -> str:
    target = "Query" if parameter.location == "query" else "Header"
    plain = inliner.plain(parameter.type)
    if not parameter.required:
        plain = f"{plain} | None" if plain != "Any" else plain
    if parameter.location == "variable":  # graphql_route binds variables by name
        return (
            f"{parameter.name}: {plain}"
            if parameter.required
            else f"{parameter.name}: {plain} = None"
        )
    annotation = f"{parameter.name}: Annotated[{plain}, {target}({py_str(parameter.wire_name)})]"
    return annotation if parameter.required else f"{annotation} = None"


def _return_type(operation: Operation) -> str:
    if operation.returns == "text":
        return "str"
    if operation.returns == "bytes":
        return "bytes"
    return operation.response_plain


def _doc(operation: Operation) -> str:
    doc = operation.summary
    if operation.deprecated:
        doc = f"{doc}\n\nDeprecated." if doc else "Deprecated."
    return doc


def _credential(scheme: AuthScheme) -> str:
    value = f"self.{scheme.attribute}"
    if scheme.style == "bearer":
        return f'lambda self: f"Bearer {{{value}}}" if {value} else None'
    if scheme.style == "basic":
        encoded = f"base64.b64encode({value}.encode()).decode()"
        return f'lambda self: f"Basic {{{encoded}}}" if {value} else None'
    return f"lambda self: {value}"


def _split_base_class(base_class: str | None) -> tuple[str, str] | None:
    """ "package.module:Class" (or "package.module.Class") as (module, class name)."""
    if base_class is None:
        return None
    module, _, name = (
        base_class.rpartition(":") if ":" in base_class else base_class.rpartition(".")
    )
    if not module or not name.isidentifier():
        raise ValueError(f"--base-class needs package.module:Class, not {base_class!r}")
    return module, name
