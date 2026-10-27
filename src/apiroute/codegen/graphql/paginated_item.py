import re

from apiroute.codegen.api_definition import Model, ModelField
from apiroute.codegen.type_ref import TypeRef


def paginated_item(models: dict[str, Model], result: TypeRef, path: str) -> TypeRef:
    """The item type of the connection at path in an operation's result model: its nodes'
    item, or its edges' node."""
    keys = path.split(".")
    current = models[result.expr]
    for index, key in enumerate(keys):
        wanted = (keys[index + 1],) if index + 1 < len(keys) else ("nodes", "edges")
        current = _model_with(models, _field(current, key).type, wanted)
    nodes = _field(current, "nodes")
    if nodes is not None:
        return _list_item(nodes.type)
    edge = _model_with(models, _field(current, "edges").type, ("node",))
    return _field(edge, "node").type


def _field(model: Model, key: str) -> ModelField | None:
    return next((f for f in model.fields if (f.alias or f.name) == key), None)


def _model_with(models: dict[str, Model], type_ref: TypeRef, keys: tuple[str, ...]) -> Model:
    """The class model type_ref names (looking through union aliases) that has one of keys."""
    pending = sorted(type_ref.models)
    while pending:
        model = models[pending.pop(0)]
        if model.alias_of is not None:
            pending.extend(sorted(model.alias_of.models))
        elif any(_field(model, key) is not None for key in keys):
            return model
    raise ValueError(f"no model along the paginate path has {' or '.join(keys)}")


def _list_item(type_ref: TypeRef) -> TypeRef:
    """X from list[X] or list[X] | None."""
    expr = type_ref.expr.removesuffix(" | None")
    inner = expr[len("list[") : -1] if expr.startswith("list[") else expr
    named = frozenset(m for m in type_ref.models if re.search(rf"\b{m}\b", inner))
    return TypeRef(inner, named)
