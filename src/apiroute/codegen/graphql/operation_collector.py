from pathlib import Path

from apiroute.codegen.graphql.collected_definition import CollectedDefinition
from apiroute.codegen.graphql.graphql_problem import GraphQLProblem
from apiroute.codegen.graphql.paginate_directive import PaginateDirective

SUFFIXES = (".graphql", ".gql")


class OperationCollector:
    """Reads every .graphql/.gql file under a directory, in path order. Files directly in it
    belong to the root client; those under a first-level subdirectory to the section named
    after it. Fragments are shared by all files.

    Problems (syntax errors, anonymous operations, subscriptions, duplicate names) are
    collected, not raised, so one run reports them all."""

    def __init__(self, directory: str):
        self._directory = Path(directory)
        self.operations: list[CollectedDefinition] = []
        self.fragments: dict[str, CollectedDefinition] = {}
        self.problems: list[GraphQLProblem] = []

    def collect(self) -> "OperationCollector":
        if not self._directory.is_dir():
            raise FileNotFoundError(f"--operations {self._directory} isn't a directory")
        files = sorted(p for p in self._directory.rglob("*") if p.suffix in SUFFIXES)
        if not files:
            raise ValueError(f"no .graphql files under {self._directory}")
        for path in files:
            self._read(path)
        return self

    def _read(self, path: Path) -> None:
        from graphql import GraphQLSyntaxError, Source, parse

        text = path.read_text(encoding="utf-8")
        try:
            document = parse(Source(text, str(path)))
        except GraphQLSyntaxError as error:
            self.problems.append(GraphQLProblem.from_error(error, str(path)))
            return
        section = self._section(path)
        for node in document.definitions:
            self._add(node, section, _comment_above(text, node.loc.start))

    def _section(self, path: Path) -> str:
        parts = path.relative_to(self._directory).parts
        return parts[0] if len(parts) > 1 else ""

    def _add(self, node, section: str, comment: str) -> None:
        from graphql import FragmentDefinitionNode, OperationDefinitionNode, OperationType

        if isinstance(node, (FragmentDefinitionNode, OperationDefinitionNode)):
            node, marks = PaginateDirective().strip(node)
        definition = CollectedDefinition(node, section, comment)
        if isinstance(node, FragmentDefinitionNode):
            for mark in marks:
                message = "@paginate belongs on a field of the operation, not in a fragment"
                self.problems.append(GraphQLProblem.at(mark.field, message))
            self._add_fragment(definition)
        elif not isinstance(node, OperationDefinitionNode):
            self.problems.append(
                GraphQLProblem.at(node, "only operations and fragments belong in operation files")
            )
        elif node.name is None:
            self.problems.append(GraphQLProblem.at(node, "operations must be named"))
        elif node.operation == OperationType.SUBSCRIPTION:
            self.problems.append(GraphQLProblem.at(node, "subscriptions aren't supported"))
        else:
            self._add_operation(self._paginated(definition, marks))

    def _paginated(self, definition: CollectedDefinition, marks: list) -> CollectedDefinition:
        for extra in marks[1:]:
            first = GraphQLProblem.at(marks[0].field, "")
            message = (
                f"an operation paginates one connection; @paginate is also at line {first.line}"
            )
            self.problems.append(GraphQLProblem.at(extra.field, message))
        return definition._replace(paginate=marks[0]) if marks else definition

    def _add_operation(self, definition: CollectedDefinition) -> None:
        name = definition.node.name.value
        for other in self.operations:
            if other.node.name.value == name:
                self.problems.append(_duplicate(definition, other, "operation"))
                return
        self.operations.append(definition)

    def _add_fragment(self, definition: CollectedDefinition) -> None:
        name = definition.node.name.value
        if name in self.fragments:
            self.problems.append(_duplicate(definition, self.fragments[name], "fragment"))
            return
        self.fragments[name] = definition


def _duplicate(definition, first, kind: str) -> GraphQLProblem:
    earlier = GraphQLProblem.at(first.node, "")
    name = definition.node.name.value
    return GraphQLProblem.at(
        definition.node,
        f"{kind} {name} is also defined at {earlier.file}:{earlier.line}:{earlier.column}",
    )


def _comment_above(text: str, start: int) -> str:
    """The # lines directly above the definition starting at offset start, without the #."""
    lines = text[:start].splitlines()
    comment: list[str] = []
    for line in reversed(lines):
        stripped = line.strip()
        if not stripped.startswith("#"):
            break
        comment.append(stripped.lstrip("#").strip())
    return "\n".join(reversed(comment)).strip()
