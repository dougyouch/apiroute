from collections.abc import Collection

from apiroute.class_declaration import declares
from apiroute.graphql.graphql_variable import GraphQLVariable
from apiroute.graphql.snake_case import snake_case


class GraphQLVariableBinder:
    """Decides which argument (or client attribute) fills each variable an operation declares.

    A variable takes the argument variables= names for it, else the argument of the same name,
    else the one named in snake_case ($repoName from repo_name), else the client attribute of
    either name. A required variable left unfilled is an error; an optional one isn't sent.
    """

    def __init__(
        self, variables: tuple[GraphQLVariable, ...], explicit: dict[str, str], owner: type
    ):
        self._variables = variables
        self._explicit = explicit
        self._owner = owner
        self._check_explicit()

    def template(self, params: Collection[str]) -> dict[str, str]:
        """The route's body template: each filled variable and the {placeholder} filling it."""
        template = {}
        for variable in self._variables:
            source = self._source(variable.name, params)
            if source is not None:
                template[variable.name] = f"{{{source}}}"
            elif variable.required:
                raise TypeError(
                    f"no argument or client attribute fills ${variable.name}; add a "
                    f"{self.param_name(variable.name)!r} parameter or map it with variables="
                )
        return template

    def param_name(self, variable: str) -> str:
        """The parameter a generated signature gives the variable."""
        return self._explicit.get(variable) or snake_case(variable)

    def _source(self, variable: str, params: Collection[str]) -> str | None:
        if variable in self._explicit:
            return self._explicit_source(variable, params)
        for name in (variable, snake_case(variable)):
            if name in params:
                return name
        for name in (variable, snake_case(variable)):
            if declares(self._owner, name):
                return name
        return None

    def _explicit_source(self, variable: str, params: Collection[str]) -> str:
        name = self._explicit[variable]
        if name not in params and not declares(self._owner, name):
            raise TypeError(f"variables= fills ${variable} from {name!r}, which is no parameter")
        return name

    def _check_explicit(self) -> None:
        declared = {variable.name for variable in self._variables}
        unknown = sorted(set(self._explicit) - declared)
        if unknown:
            names = ", ".join(f"${name}" for name in unknown)
            raise ValueError(f"variables= maps {names}, which the operation doesn't declare")
