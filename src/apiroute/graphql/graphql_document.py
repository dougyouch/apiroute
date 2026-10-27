from apiroute.graphql.graphql_operation import GraphQLOperation
from apiroute.graphql.graphql_tokens import tokenize
from apiroute.graphql.graphql_variable import GraphQLVariable

OPERATION_TYPES = ("query", "mutation", "subscription")
_CLOSING = {"{": "}", "(": ")", "[": "]"}


class GraphQLDocument:
    """Reads a document's operations: type, name and variable definitions. Selection sets,
    arguments and fragments are skipped, not checked; the server (or graphql-core, when
    installed) does that."""

    def __init__(self, text: str):
        self.text = text
        self._tokens = tokenize(text)
        self._position = 0
        self.operations = self._read_definitions()

    def operation(self, name: str | None = None) -> GraphQLOperation:
        """The operation named name, or the only one when name is None."""
        if name is not None:
            return self._named(name)
        if len(self.operations) != 1:
            raise ValueError("the document has several operations; pick one with operation_name")
        return self.operations[0]

    def _named(self, name: str) -> GraphQLOperation:
        for operation in self.operations:
            if operation.name == name:
                return operation
        if len(self.operations) == 1 and self.operations[0].name is None:
            return self.operations[0]  # name only labels an anonymous operation
        raise ValueError(f"the document has no operation named {name!r}")

    def _read_definitions(self) -> list[GraphQLOperation]:
        operations = []
        while not self._at_end():
            token = self._peek()
            if token == "{":
                self._skip_balanced()
                operations.append(GraphQLOperation("query", None, ()))
            elif token in OPERATION_TYPES:
                operations.append(self._read_operation())
            elif token == "fragment":
                self._skip_fragment()
            else:
                raise ValueError(f"expected an operation or fragment, found {token!r}")
        if not operations:
            raise ValueError("the document has no operation")
        return operations

    def _read_operation(self) -> GraphQLOperation:
        operation_type = self._next()
        if operation_type == "subscription":
            raise ValueError("subscriptions aren't supported")
        name = self._next() if self._is_name(self._peek()) else None
        variables = self._read_variables() if self._peek() == "(" else ()
        self._skip_until_selection_set()
        return GraphQLOperation(operation_type, name, variables)

    def _read_variables(self) -> tuple[GraphQLVariable, ...]:
        self._expect("(")
        variables = []
        while self._peek() != ")":
            variables.append(self._read_variable())
        self._expect(")")
        return tuple(variables)

    def _read_variable(self) -> GraphQLVariable:
        self._expect("$")
        name = self._next()
        self._expect(":")
        type_ = self._read_type()
        has_default = self._peek() == "="
        if has_default:
            self._next()
            self._skip_value()
        self._skip_directives()
        return GraphQLVariable(name, type_, type_.endswith("!") and not has_default, has_default)

    def _read_type(self) -> str:
        if self._peek() == "[":
            self._next()
            inner = self._read_type()
            self._expect("]")
            type_ = f"[{inner}]"
        else:
            type_ = self._next()
        if self._peek() == "!":
            type_ += self._next()
        return type_

    def _skip_fragment(self) -> None:
        self._next()
        self._skip_until_selection_set()

    def _skip_until_selection_set(self) -> None:
        """Skips directives (whose arguments may hold braces) up to and over the selection set."""
        while self._peek() != "{":
            if self._peek() == "(":
                self._skip_balanced()
            else:
                self._next()
        self._skip_balanced()

    def _skip_directives(self) -> None:
        while self._peek() == "@":
            self._next()
            self._next()
            if self._peek() == "(":
                self._skip_balanced()

    def _skip_value(self) -> None:
        if self._peek() in _CLOSING:
            self._skip_balanced()
        else:
            self._next()

    def _skip_balanced(self) -> None:
        stack = [_CLOSING[self._next()]]
        while stack:
            token = self._next()
            if token in _CLOSING:
                stack.append(_CLOSING[token])
            elif token == stack[-1]:
                stack.pop()
            elif token in _CLOSING.values():
                raise ValueError(f"unbalanced {token!r}")

    def _expect(self, token: str) -> None:
        found = self._next()
        if found != token:
            raise ValueError(f"expected {token!r}, found {found!r}")

    def _next(self) -> str:
        if self._at_end():
            raise ValueError("the document ends early")
        token = self._tokens[self._position]
        self._position += 1
        return token

    def _peek(self) -> str | None:
        return None if self._at_end() else self._tokens[self._position]

    def _at_end(self) -> bool:
        return self._position >= len(self._tokens)

    @staticmethod
    def _is_name(token: str | None) -> bool:
        return token is not None and (token[0].isalpha() or token[0] == "_")
