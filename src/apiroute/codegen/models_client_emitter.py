import re

from apiroute.codegen.api_definition import ApiDefinition, Group, Operation, Parameter
from apiroute.codegen.generated_header import generated_header
from apiroute.codegen.import_order import import_names
from apiroute.codegen.model_placement import operation_models
from apiroute.codegen.python_literals import py_str
from apiroute.codegen.source_writer import SourceWriter


def models_class_name(group: Group) -> str:
    """GitHubApi -> GitHubApiModels, IssuesSection -> IssuesModels"""
    return f"{group.class_name.removesuffix('Section')}Models"


class ModelsClientEmitter:
    """Writes a level's models/client.py: the .models view, whose methods take request models
    and return response models by calling the dict route of the same name."""

    def __init__(
        self,
        definition: ApiDefinition,
        group: Group,
        version: str,
    ):
        self._definition = definition
        self._group = group
        self._version = version

    def source(self) -> str:
        out = SourceWriter()
        out.line(generated_header(self._version, self._definition.source))
        out.docstring(f"Typed versions of {self._group.class_name}'s routes.")
        out.line()
        out.line("from __future__ import annotations")
        out.line()
        signatures = self._signatures_text()
        used = self._used_models()
        typing_names = [n for n in ("Any", "Literal") if re.search(rf"\b{n}\b", signatures)]
        if used:
            typing_names.append("TYPE_CHECKING")
        standard = []
        if re.search(r"\bIterator\b", signatures):
            standard.append("from collections.abc import Iterator")
        if typing_names:
            standard.append(f"from typing import {import_names(typing_names)}")
        if standard:
            out.lines(*standard, "")
        out.line("from apiroute import TypedClient")
        if used:
            # for type checkers only: at run time each response type is looked up in .models
            # on the method's first call, so a call imports just the models it returns
            out.line()
            out.line("if TYPE_CHECKING:")
            with out.indented():
                out.line(f"from .models import {import_names(used)}")
        out.lines("", "")
        out.line(f"class {models_class_name(self._group)}(TypedClient):")
        with out.indented():
            out.docstring(f"Typed versions of {self._group.class_name}'s routes.")
            for operation in self._group.operations:
                out.line()
                self._method(out, operation)
        return out.text()

    def _signatures_text(self) -> str:
        texts = []
        for operation in self._group.operations:
            texts += _signature(operation)
            texts.append(_returned(operation))
        return " ".join(texts)

    def _used_models(self) -> set[str]:
        used: set[str] = set()
        for operation in self._group.operations:
            used |= operation_models(operation)
        return used

    def _method(self, out: SourceWriter, operation: Operation) -> None:
        response = operation.response
        returned = _returned(operation)
        out.line(f"def {operation.name}(")
        with out.indented():
            out.line("self,")
            for parameter in _signature(operation):
                out.line(f"{parameter},")
        out.line(f") -> {returned}:")
        with out.indented():
            if operation.summary:
                out.docstring(operation.summary)
            response_type = py_str(response.expr) if response else "None"
            arguments = ", ".join([py_str(operation.name), response_type, *_forwarded(operation)])
            call = "_paginate" if _is_paginated(operation) else "_call"
            out.line(f"return self.{call}({arguments})")


def _signature(operation: Operation) -> list[str]:
    path = [p for p in operation.parameters if p.location == "path"]
    rest = sorted(
        (p for p in operation.parameters if p.location != "path"), key=lambda p: not p.required
    )
    keyword = [_typed(p) for p in rest]
    if operation.body is not None:
        body = f"body: {operation.body.type.expr}"
        if operation.body.required:
            keyword.insert(0, body)
        else:
            keyword.append(f"{body} | None = None")
    return [f"{p.name}: {p.type.expr}" for p in path] + (["*", *keyword] if keyword else [])


def _typed(parameter: Parameter) -> str:
    if parameter.required:
        return f"{parameter.name}: {parameter.type.expr}"
    return f"{parameter.name}: {parameter.type.optional().expr} = None"


def _forwarded(operation: Operation) -> list[str]:
    names = [p.name for p in operation.parameters]
    if operation.body is not None:
        names.append("body")
    return [f"{name}={name}" for name in names]


def _returned(operation: Operation) -> str:
    if operation.response is None:
        return _plain_return(operation)
    if _is_paginated(operation):
        return f"Iterator[{operation.response.expr}]"
    return operation.response.expr


def _is_paginated(operation: Operation) -> bool:
    return operation.graphql is not None and operation.graphql.paginate is not None


def _plain_return(operation: Operation) -> str:
    if operation.response_plain == "None":
        return "None"
    return {"text": "str", "bytes": "bytes"}.get(operation.returns, "Any")
