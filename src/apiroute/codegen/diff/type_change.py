import ast

from apiroute.codegen.diff.api_change import ADDITION, BREAKING


def type_change(old: str, new: str) -> str | None:
    """How a type expression changed: None when it didn't, ADDITION when it only gained Literal
    values (an enum taking more values), else BREAKING."""
    if old == new:
        return None
    old_values, new_values = _literal_values(old), _literal_values(new)
    if old_values is not None and new_values is not None and old_values < new_values:
        return ADDITION
    return BREAKING


def _literal_values(expr: str) -> frozenset[object] | None:
    """The values of a Literal[...] (optionally | None), or None for any other expression."""
    try:
        tree = ast.parse(expr, mode="eval").body
    except SyntaxError:
        return None
    values: set[object] = set()
    for part in _union_parts(tree):
        if isinstance(part, ast.Constant) and part.value is None:
            values.add(None)
        elif isinstance(part, ast.Subscript) and getattr(part.value, "id", None) == "Literal":
            items = part.slice.elts if isinstance(part.slice, ast.Tuple) else [part.slice]
            if not all(isinstance(item, ast.Constant) for item in items):
                return None
            values.update(item.value for item in items if isinstance(item, ast.Constant))
        else:
            return None
    return frozenset(values)


def _union_parts(node: ast.expr) -> list[ast.expr]:
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.BitOr):
        return [*_union_parts(node.left), *_union_parts(node.right)]
    return [node]
