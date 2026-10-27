from typing import Any

from apiroute.codegen.graphql.collected_definition import CollectedDefinition
from apiroute.codegen.graphql.field_collector import FieldCollector
from apiroute.codegen.graphql.graphql_problem import GraphQLProblem
from apiroute.codegen.graphql.operation_collector import OperationCollector
from apiroute.codegen.graphql.typename_inserter import TypenameInserter


class OperationDocuments:
    """Each operation's document (the operation and every fragment it uses), validated
    against the schema as read, and printed as sent once __typename is added where needed."""

    def __init__(self, schema: Any, collected: OperationCollector):
        self._schema = schema
        self._collected = collected
        self._fragment_nodes = {name: d.node for name, d in collected.fragments.items()}
        self.collector = FieldCollector(schema, self._fragment_nodes)
        self._inserter = TypenameInserter(schema, self.collector)
        self._prepared = {
            name: self._inserter.definition(n) for name, n in self._fragment_nodes.items()
        }

    def problems(self) -> list[GraphQLProblem]:
        """What makes an operation invalid against the schema, each reported once."""
        from graphql import validate

        found: list[GraphQLProblem] = []
        for operation in self._collected.operations:
            for error in validate(self._schema, self._document(operation.node)):
                found.append(GraphQLProblem.from_error(error))
        return _unique(found)

    def warnings(self) -> list[GraphQLProblem]:
        """Deprecated fields, arguments and enum values in use, and unused fragments."""
        from graphql import validate
        from graphql.validation import NoDeprecatedCustomRule

        found: list[GraphQLProblem] = []
        used: set[str] = set()
        for operation in self._collected.operations:
            used |= self.fragments_used(operation.node)
            rules = [NoDeprecatedCustomRule]
            for error in validate(self._schema, self._document(operation.node), rules):
                found.append(GraphQLProblem.from_error(error))
        for name, fragment in self._collected.fragments.items():
            if name not in used:
                found.append(GraphQLProblem.at(fragment.node, f"fragment {name} is never used"))
        return _unique(found)

    def prepared(self, operation: CollectedDefinition) -> tuple[Any, dict[str, Any]]:
        """The operation with __typename added where needed, and the fragments it uses
        (prepared the same way), by name."""
        used = sorted(self.fragments_used(operation.node))
        return self._inserter.definition(operation.node), {n: self._prepared[n] for n in used}

    def text(self, operation: CollectedDefinition) -> str:
        """The document sent for the operation: it, then its fragments by name."""
        from graphql import DocumentNode, print_ast

        node, fragments = self.prepared(operation)
        return print_ast(DocumentNode(definitions=(node, *fragments.values())))

    def fragments_used(self, node: Any) -> set[str]:
        """The fragments node spreads, directly or through other fragments."""
        used: set[str] = set()
        pending = [node]
        while pending:
            for name in _spreads(pending.pop()):
                if name not in used and name in self._fragment_nodes:
                    used.add(name)
                    pending.append(self._fragment_nodes[name])
        return used

    def _document(self, node: Any) -> Any:
        from graphql import DocumentNode

        fragments = [self._fragment_nodes[n] for n in sorted(self.fragments_used(node))]
        return DocumentNode(definitions=(node, *fragments))


def _spreads(node: Any) -> list[str]:
    from graphql import FragmentSpreadNode, Visitor, visit

    names: list[str] = []

    class Spreads(Visitor):
        def enter_fragment_spread(self, spread: FragmentSpreadNode, *_: Any) -> None:
            names.append(spread.name.value)

    visit(node, Spreads())
    return names


def _unique(problems: list[GraphQLProblem]) -> list[GraphQLProblem]:
    return list(dict.fromkeys(problems))
