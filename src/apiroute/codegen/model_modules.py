from dataclasses import dataclass

from apiroute.codegen.api_definition import ApiDefinition
from apiroute.codegen.python_names import snake_case, unique


@dataclass(frozen=True)
class SchemaModule:
    folder: str  # the group the module belongs to; "" for the root
    name: str  # the file name under <folder>/models/schemas/, without .py
    models: tuple[str, ...]


class ModelModules:
    """Splits each folder's models into schemas/ modules: one per model, except that models
    referring to each other in a cycle share one, so modules import each other without cycles.
    A program then imports only the models it uses and what they depend on."""

    def __init__(self, definition: ApiDefinition, placement: dict[str, str]):
        self._definition = definition
        self._placement = placement

    def modules(self) -> dict[str, SchemaModule]:
        """Model name -> the module that defines it."""
        by_model: dict[str, SchemaModule] = {}
        taken: dict[str, set[str]] = {}
        for component in sorted(self._components(), key=lambda c: sorted(c)[0]):
            members = tuple(sorted(component))
            folder = self._placement[members[0]]
            name = unique(snake_case(members[0]), taken.setdefault(folder, set()), frozenset())
            module = SchemaModule(folder, name, members)
            for model in members:
                by_model[model] = module
        return by_model

    def dependencies(self, name: str) -> set[str]:
        model = self._definition.models[name]
        if model.alias_of is not None:
            names = set(model.alias_of.models)
        else:
            names = {dep for field in model.fields for dep in field.type.models}
        return {dep for dep in names if dep in self._definition.models}

    def _components(self) -> list[set[str]]:
        """Strongly connected components of the model graph (Tarjan's algorithm, iterative,
        since big specs nest deeper than Python's recursion limit)."""
        index: dict[str, int] = {}
        low: dict[str, int] = {}
        on_stack: set[str] = set()
        stack: list[str] = []
        components: list[set[str]] = []
        counter = 0
        for start in sorted(self._definition.models):
            if start in index:
                continue
            work = [(start, iter(sorted(self.dependencies(start))))]
            index[start] = low[start] = counter
            counter += 1
            stack.append(start)
            on_stack.add(start)
            while work:
                node, children = work[-1]
                child = next(children, None)
                if child is None:
                    work.pop()
                    if work:
                        low[work[-1][0]] = min(low[work[-1][0]], low[node])
                    if low[node] == index[node]:
                        component = set()
                        while True:
                            member = stack.pop()
                            on_stack.discard(member)
                            component.add(member)
                            if member == node:
                                break
                        components.append(component)
                elif child not in index:
                    index[child] = low[child] = counter
                    counter += 1
                    stack.append(child)
                    on_stack.add(child)
                    work.append((child, iter(sorted(self.dependencies(child)))))
                elif child in on_stack:
                    low[node] = min(low[node], index[child])
        return components
