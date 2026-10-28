import shutil
from importlib.metadata import version
from pathlib import Path

from apiroute.codegen.api_definition import ApiDefinition, Group
from apiroute.codegen.dict_client_emitter import DictClientEmitter
from apiroute.codegen.generated_header import MARKER, generated_header
from apiroute.codegen.model_modules import ModelModules
from apiroute.codegen.model_placement import ModelPlacement, operation_models
from apiroute.codegen.models_client_emitter import ModelsClientEmitter
from apiroute.codegen.models_index_emitter import ModelsIndexEmitter
from apiroute.codegen.schema_module_emitter import SchemaModuleEmitter
from apiroute.codegen.section_path import section_folder


class PackageEmitter:
    """Writes the generated package:

        <out>/__init__.py, client.py              the root client (dicts)
        <out>/<tag>/client.py                     one Section per tag (dicts); a dotted
                                                  section (issuing.cards) nests folders
        <out>/[<tag>/]models/client.py           the .models view, when with_models
        <out>/[<tag>/]models/models.py           a lazy index of the level's models
        <out>/[<tag>/]models/schemas/*.py        one module per model (or cycle of models)

    Regenerating into the same directory first removes every file this generator wrote
    (they start with MARKER), so tags dropped from the spec don't linger; a directory that
    isn't a previous apiroute package is refused rather than overwritten.
    """

    def __init__(self, definition: ApiDefinition, with_models: bool):
        self._definition = definition
        self._with_models = with_models
        self._version = version("apiroute")

    def files(self) -> dict[str, str]:
        """Relative path -> source."""
        files = {"__init__.py": self._init_source(), "client.py": self._client(self._root)}
        for group in self._definition.groups:
            folder = section_folder(group.name)
            files[f"{folder}/__init__.py"] = self._marker_only()
            files[f"{folder}/client.py"] = self._client(group)
        if self._with_models:
            files.update(self._models_files())
        return files

    def write(self, out_dir: Path) -> list[Path]:
        self._clear_previous(out_dir)
        written = []
        for relative, source in self.files().items():
            path = out_dir / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(source)
            written.append(path)
        return written

    @property
    def _root(self) -> Group:
        return self._definition.root

    def _client(self, group: Group) -> str:
        emitter = DictClientEmitter(self._definition, group, self._with_models, self._version)
        return emitter.source()

    def _models_files(self) -> dict[str, str]:
        placement = ModelPlacement(self._definition).place()
        splitter = ModelModules(self._definition, placement)
        modules = splitter.modules()
        files: dict[str, str] = {}
        for group in [self._root, *self._definition.groups]:
            folder = _models_folder(group.name)
            files[f"{folder}/__init__.py"] = self._marker_only()
            client = ModelsClientEmitter(self._definition, group, self._version)
            files[f"{folder}/client.py"] = client.source()
            names = {n for n, owner in placement.items() if owner == group.name}
            for operation in group.operations:
                names |= operation_models(operation)
            index = ModelsIndexEmitter(self._definition, group, names, modules, self._version)
            files[f"{folder}/models.py"] = index.source()
            files[f"{folder}/schemas/__init__.py"] = self._marker_only()
        for module in {id(m): m for m in modules.values()}.values():
            emitter = SchemaModuleEmitter(
                self._definition, module, modules, splitter.dependencies, self._version
            )
            files[f"{_models_folder(module.folder)}/schemas/{module.name}.py"] = emitter.source()
        return files

    def _init_source(self) -> str:
        name = self._definition.client_name
        return (
            f"{self._header()}\n"
            f'"""{self._definition.title or name}."""\n\n'
            f"from .client import {name}\n\n"
            f'__all__ = ["{name}"]\n'
        )

    def _marker_only(self) -> str:
        return f"{self._header()}\n"

    def _header(self) -> str:
        return generated_header(self._version, self._definition.source)

    def _clear_previous(self, out_dir: Path) -> None:
        if not out_dir.exists():
            return
        if any(out_dir.iterdir()) and not _is_generated(out_dir / "client.py"):
            raise FileExistsError(
                f"{out_dir} exists and isn't a package apiroute generated; "
                "choose an empty or new directory"
            )
        for path in sorted(out_dir.rglob("*.py"), reverse=True):
            if _is_generated(path):
                path.unlink()
        for cache in out_dir.rglob("__pycache__"):
            shutil.rmtree(cache, ignore_errors=True)
        for directory in sorted((p for p in out_dir.rglob("*") if p.is_dir()), reverse=True):
            if not any(directory.iterdir()):
                directory.rmdir()


def _models_folder(group_name: str) -> str:
    return f"{section_folder(group_name)}/models" if group_name else "models"


def _is_generated(path: Path) -> bool:
    if not path.is_file():
        return False
    with path.open() as file:
        return file.readline().startswith(MARKER)
