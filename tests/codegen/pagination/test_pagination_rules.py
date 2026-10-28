import json

import pytest

from apiroute.codegen.pagination.operation_facts import OperationFacts
from apiroute.codegen.pagination.pagination_rules import PaginationRules
from tests.codegen.conftest import FIXTURES

FACTS = OperationFacts("SearchHits", "GET", frozenset({"page"}), True, frozenset())


def test_loads_yaml_and_labels_rules_by_position_and_name():
    rules = PaginationRules.load(str(FIXTURES / "paging.rules.yaml"))
    labels = [rule.label.rsplit(": ", 1)[1] for rule in rules.rules]
    assert labels == ["rule 1 (Stripe lists)", "rule 2 (GitHub lists)", "rule 3"]


def test_first_match_wins_and_is_counted(tmp_path):
    path = tmp_path / "rules.json"
    path.write_text(
        json.dumps(
            [
                {"operations": ["Search*"], "paginate": {"type": "offset"}},
                {"response": "array", "paginate": {"type": "next_url"}},
                {"operations": ["Nope*"], "paginate": {"type": "page"}},
            ]
        )
    )
    rules = PaginationRules.load(str(path))
    assert rules.match(FACTS).strategy.class_name == "Offset"
    assert rules.report() == [
        f"{path}: rule 1: 1 operation",
        f"{path}: rule 2: 0 operations",
        f"{path}: rule 3: 0 operations",
    ]
    assert rules.warnings() == [
        f"{path}: rule 2 matched no operation",
        f"{path}: rule 3 matched no operation",
    ]


def test_a_file_that_is_not_a_list(tmp_path):
    path = tmp_path / "rules.json"
    path.write_text("{}")
    with pytest.raises(ValueError, match="expected a list of pagination rules"):
        PaginationRules.load(str(path))
