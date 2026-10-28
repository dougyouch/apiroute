import json
from pathlib import Path

from apiroute.codegen.pagination.operation_facts import OperationFacts
from apiroute.codegen.pagination.pagination_rule import PaginationRule


class PaginationRules:
    """The ordered rules of a --pagination file (JSON, or YAML with pyyaml installed); each
    operation takes the first rule that matches it:

        - has_parameter: [starting_after]
          response: {has: [data, has_more]}
          paginate: {type: item_cursor, items: data}
    """

    def __init__(self, rules: list[PaginationRule]):
        self.rules = rules

    @classmethod
    def load(cls, path: str) -> "PaginationRules":
        raw = _parsed(Path(path))
        if not isinstance(raw, list):
            raise ValueError(f"{path}: expected a list of pagination rules")
        return cls([PaginationRule(rule, f"{path}: rule {n}") for n, rule in enumerate(raw, 1)])

    def match(self, facts: OperationFacts) -> PaginationRule | None:
        for rule in self.rules:
            if rule.matches(facts):
                rule.matched += 1
                return rule
        return None

    def report(self) -> list[str]:
        return [
            f"{rule.label}: {rule.matched} operation{'' if rule.matched == 1 else 's'}"
            for rule in self.rules
        ]

    def warnings(self) -> list[str]:
        return [f"{rule.label} matched no operation" for rule in self.rules if not rule.matched]


def _parsed(path: Path) -> object:
    text = path.read_text()
    if path.suffix == ".json" or text.lstrip()[:1] in ("[", "{"):
        return json.loads(text)
    try:
        import yaml
    except ImportError as error:
        raise RuntimeError(
            "YAML pagination rules need PyYAML: pip install apiroute[codegen]"
        ) from error
    return yaml.safe_load(text)
