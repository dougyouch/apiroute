from apiroute.codegen.api_definition import ApiDefinition, Group
from apiroute.codegen.generated_header import generated_header
from apiroute.codegen.import_order import import_names
from apiroute.codegen.model_modules import SchemaModule
from apiroute.codegen.python_literals import py_str
from apiroute.codegen.section_path import section_depth
from apiroute.codegen.source_writer import SourceWriter


class ModelsIndexEmitter:
    """Writes a level's models/models.py: every model this level owns or its operations use,
    each imported from its schemas/ module only when first accessed. Type checkers read the
    TYPE_CHECKING imports, so `from gh.repos.models.models import Repository` is fully typed."""

    def __init__(
        self,
        definition: ApiDefinition,
        group: Group,
        names: set[str],
        modules: dict[str, SchemaModule],
        version: str,
    ):
        self._definition = definition
        self._group = group
        self._names = sorted(names)
        self._modules = modules
        self._version = version

    def source(self) -> str:
        out = SourceWriter()
        out.line(generated_header(self._version, self._definition.source))
        title = f"the {self._group.name} endpoints" if self._group.name else "the API"
        out.line("# ruff: noqa: E501  (model names and module paths can't be wrapped)")
        out.docstring(f"Models for {title}, each imported on first use.")
        out.line()
        if self._names:
            out.line("from typing import TYPE_CHECKING")
            out.line()
        out.line("from apiroute import lazy_exports")
        if self._names:
            out.line()
            out.line("if TYPE_CHECKING:")
            with out.indented():
                for path, names in self._grouped():
                    out.line(f"from {path} import {import_names(names)}")
        out.line()
        if not self._names:
            # a level without models: mypy can't infer an empty list's type
            out.line("__all__: list[str] = []")
        else:
            out.line("__all__ = [")
            with out.indented():
                for name in self._names:
                    out.line(f"{py_str(name)},")
            out.line("]")
        out.line()
        out.line("__getattr__, __dir__ = lazy_exports(")
        with out.indented():
            out.line("__name__,")
            out.line("{")
            with out.indented():
                for name in self._names:
                    out.line(f"{py_str(name)}: {py_str(self._path(name))},")
            out.line("},")
        out.line(")")
        return out.text()

    def _path(self, name: str) -> str:
        module = self._modules[name]
        if module.folder == self._group.name:
            return f".schemas.{module.name}"
        # a root model, from a section's index: up through models/ and the section's folders
        return "." * (section_depth(self._group.name) + 2) + f"models.schemas.{module.name}"

    def _grouped(self) -> list[tuple[str, list[str]]]:
        by_path: dict[str, list[str]] = {}
        for name in self._names:
            by_path.setdefault(self._path(name), []).append(name)
        # ruff orders relative imports furthest first: more leading dots, then by name
        return sorted(
            by_path.items(), key=lambda item: (len(item[0].lstrip(".")) - len(item[0]), item[0])
        )
