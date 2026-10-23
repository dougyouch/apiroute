from dataclasses import dataclass, field


@dataclass(frozen=True)
class TypeRef:
    """A Python type expression for generated code, and the models it names.

    expr is source text such as "list[Repo] | None"; models lists the generated model
    classes it mentions, so the emitter knows what each file must import.
    """

    expr: str
    models: frozenset[str] = field(default_factory=frozenset)

    def optional(self) -> "TypeRef":
        if self.expr == "Any" or self.expr.endswith("| None"):
            return self
        return TypeRef(f"{self.expr} | None", self.models)

    @staticmethod
    def of(expr: str, *parts: "TypeRef") -> "TypeRef":
        """expr built from parts, carrying the models they mention."""
        models = frozenset().union(*(part.models for part in parts))
        return TypeRef(expr, models)

    @staticmethod
    def model(name: str) -> "TypeRef":
        return TypeRef(name, frozenset({name}))


ANY = TypeRef("Any")
