import pytest

from apiroute.codegen.openapi.openapi_reader import OpenApiReader
from apiroute.codegen.pagination.pagination_rules import PaginationRules
from tests.codegen.conftest import FIXTURES


def read(rules="paging.rules.yaml"):
    loaded = None if rules is None else PaginationRules.load(str(FIXTURES / rules))
    return OpenApiReader(str(FIXTURES / "paging.yaml"), "PagingApi", pagination=loaded).read()


def operations(definition):
    return {
        operation.operation_id: operation
        for group in [definition.root, *definition.groups]
        for operation in group.operations
    }


def test_rules_pick_operations_and_their_item_types():
    paging = {
        operation_id: (o.all_pages.source(), o.all_pages.item and o.all_pages.item.expr)
        for operation_id, o in operations(read()).items()
        if o.all_pages is not None
    }
    assert paging == {
        "GetCustomers": ("ItemCursor()", "Customer"),
        "issues/list-for-repo": ("NextUrl()", "Issue"),
        "SearchHits": ('Offset(total="total", items="hits")', "SearchHitsResponseHitsItem"),
        "ListEvents": ('Offset(param="offset", limit="limit", items="data.items")', "Event"),
    }


def test_the_extension_is_read_without_rules_and_a_bad_one_is_a_warning():
    definition = read(rules=None)
    assert [o for o, op in operations(definition).items() if op.all_pages] == ["ListEvents"]
    assert definition.warnings == [
        "ListFeed: x-speakeasy-pagination: the JSONPath '$.data[*]' isn't a path of dotted "
        "keys; not paginated"
    ]


def test_an_inline_item_is_not_mapped_twice():
    definition = read()
    assert "SearchHitsResponseHitsItem" in definition.models
    assert not any(name.startswith("SearchHitsItem") for name in definition.models)


def test_an_items_path_that_is_not_an_array_stops_generation(tmp_path):
    rules = tmp_path / "rules.yaml"
    rules.write_text(
        "- operations: [GetCustomers]\n  paginate: {type: item_cursor, items: object}\n"
    )
    with pytest.raises(ValueError, match="GetCustomers: .*rule 1: items 'object' isn't an array"):
        OpenApiReader(
            str(FIXTURES / "paging.yaml"),
            "PagingApi",
            pagination=PaginationRules.load(str(rules)),
        ).read()


def test_a_rule_matching_nothing_is_a_warning(tmp_path):
    rules = tmp_path / "rules.yaml"
    rules.write_text("- operations: [Nope*]\n  paginate: {type: page}\n")
    definition = OpenApiReader(
        str(FIXTURES / "paging.yaml"), "PagingApi", pagination=PaginationRules.load(str(rules))
    ).read()
    assert f"{rules}: rule 1 matched no operation" in definition.warnings
