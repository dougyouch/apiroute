import ast
import dataclasses

from apiroute.codegen.api_definition import ApiDefinition
from apiroute.codegen.type_ref import TypeRef


class OpenEnums:
    """Lets every enum in the models also take values the spec doesn't list (--open-enums),
    for APIs that send them: Literal["N", "S"] becomes Literal["N", "S"] | str. Literals of a
    single value stay closed, since they tag the members of unions (type: "Feature")."""

    def apply(self, definition: ApiDefinition) -> None:
        for model in definition.models.values():
            model.fields = [
                dataclasses.replace(field, type=opened(field.type)) for field in model.fields
            ]
            if model.alias_of is not None:
                model.alias_of = opened(model.alias_of)


def opened(type_ref: TypeRef) -> TypeRef:
    if "Literal[" not in type_ref.expr:
        return type_ref
    tree = _Opener().visit(ast.parse(type_ref.expr, mode="eval"))
    return TypeRef(ast.unparse(tree), type_ref.models)


class _Opener(ast.NodeTransformer):
    def visit_Subscript(self, node: ast.Subscript) -> ast.AST:
        if not (isinstance(node.value, ast.Name) and node.value.id == "Literal"):
            return self.generic_visit(node)
        values = node.slice.elts if isinstance(node.slice, ast.Tuple) else [node.slice]
        kinds = {type(value.value) for value in values if isinstance(value, ast.Constant)}
        if len(values) < 2 or len(kinds) != 1 or kinds - {str, int}:
            return node
        return ast.BinOp(node, ast.BitOr(), ast.Name(kinds.pop().__name__))
