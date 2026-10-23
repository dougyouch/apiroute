import re

from apiroute.codegen.api_definition import ApiDefinition
from apiroute.codegen.type_ref import TypeRef


class AliasInliner:
    """Writes a type without naming any model, for the dict layer: aliases that end in plain
    types (PetStatus = Literal["available", "sold"]) are spelled out, and anything that
    still involves a model class becomes Any."""

    def __init__(self, definition: ApiDefinition):
        self._models = definition.models

    def plain(self, type_ref: TypeRef) -> str:
        expr = type_ref.expr
        for _ in range(10):  # aliases of aliases, a few levels deep
            names = [n for n in type_ref.models if n in re.findall(r"\w+", expr)]
            if not names:
                return expr
            for name in names:
                model = self._models.get(name)
                if model is None or model.alias_of is None:
                    return "Any"
                spelled = model.alias_of.expr
                if " | " in spelled and expr != name:
                    spelled = f"({spelled})"  # keeps list[A | B] from reading as list[A] | B
                expr = re.sub(rf"\b{name}\b", spelled, expr)
                type_ref = TypeRef(expr, type_ref.models | model.alias_of.models)
        return "Any"
