from apiroute.codegen.api_definition import ApiDefinition, Webhook
from apiroute.codegen.generated_header import generated_header
from apiroute.codegen.import_order import import_names
from apiroute.codegen.model_modules import SchemaModule
from apiroute.codegen.python_literals import py_str
from apiroute.codegen.source_writer import SourceWriter

_TYPING_NAMES = ("Annotated", "Any", "Literal")


class WebhooksEmitter:
    """Writes webhooks.py for the webhooks a spec declares: a function per webhook parsing a
    request body into its payload, and WEBHOOKS mapping the spec's names to them. The package
    root's returns dicts; models/webhooks.py (with modules, the schema modules by model name)
    returns the payload models."""

    def __init__(
        self,
        definition: ApiDefinition,
        version: str,
        modules: dict[str, SchemaModule] | None = None,
    ):
        self._definition = definition
        self._version = version
        self._modules = modules

    def source(self) -> str:
        out = SourceWriter()
        out.line(generated_header(self._version, self._definition.source))
        if self._modules is not None:
            out.line("# ruff: noqa: E501  (model module paths can't be wrapped)")
        title = self._definition.title or self._definition.client_name
        out.docstring(
            f"Webhooks {title} sends: each function parses a request body into its payload. "
            "Check the request's signature first, e.g. with apiroute.webhooks.HmacSignature."
        )
        out.line()
        out.line("from __future__ import annotations")
        out.line()
        typing_names = [n for n in _TYPING_NAMES if self._mentions(n)]
        out.line(f"from typing import {import_names(typing_names)}")
        out.line()
        out.line("from apiroute.webhooks import parse_payload")
        imports = self._model_imports()
        if imports:
            out.line()
            out.lines(*imports)
        names = [w.name for w in self._definition.webhooks]
        out.line()
        out.line(f"__all__ = [{', '.join(py_str(n) for n in ['WEBHOOKS', *names])}]")
        for webhook in self._definition.webhooks:
            out.lines("", "")
            self._function(out, webhook)
        out.lines("", "")
        out.line("# The spec's name for each webhook -> the function parsing its payload")
        out.line("WEBHOOKS = {")
        with out.indented():
            for webhook in self._definition.webhooks:
                out.line(f"{py_str(webhook.wire_name)}: {webhook.name},")
        out.line("}")
        return out.text()

    def _function(self, out: SourceWriter, webhook: Webhook) -> None:
        typed = self._modules is not None and webhook.payload is not None
        body_type = "bytes | str | dict[str, Any] | list[Any]" if typed else "bytes | str"
        returns = webhook.payload.expr if typed and webhook.payload else webhook.payload_plain
        out.line(f"def {webhook.name}(body: {body_type}) -> {returns}:")
        with out.indented():
            out.docstring(webhook.summary or f"The payload of the {webhook.wire_name} webhook.")
            model = f", {webhook.payload.expr}" if typed and webhook.payload else ""
            out.line(f"return parse_payload(body{model})")

    def _mentions(self, name: str) -> bool:
        if name == "Any":
            return True  # the dict layer's types, and the models layer's body parameter
        separators = str.maketrans("[],|()", "      ")
        for webhook in self._definition.webhooks:
            expr = webhook.payload.expr if self._typed(webhook) else webhook.payload_plain
            if name in str(expr).translate(separators).split():
                return True
        return False

    def _typed(self, webhook: Webhook) -> bool:
        return self._modules is not None and webhook.payload is not None

    def _model_imports(self) -> list[str]:
        if self._modules is None:
            return []
        by_module: dict[str, set[str]] = {}
        for webhook in self._definition.webhooks:
            if webhook.payload is None:
                continue
            for name in webhook.payload.models:
                module = self._modules[name]
                path = f".schemas.{module.name}"
                if module.folder:
                    path = f"..{module.folder}.models.schemas.{module.name}"
                by_module.setdefault(path, set()).add(name)
        ordered = sorted(by_module, key=lambda p: (len(p.lstrip(".")) - len(p), p))
        return [f"from {path} import {import_names(by_module[path])}" for path in ordered]
