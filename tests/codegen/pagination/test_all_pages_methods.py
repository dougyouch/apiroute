import pytest

from apiroute.codegen.api_definition import ApiDefinition, Group, Operation, RestPagination
from apiroute.codegen.pagination.all_pages_methods import AllPagesMethods
from apiroute.codegen.type_ref import TypeRef

PAGES = RestPagination("ItemCursor", {}, TypeRef.model("Customer"), "dict[str, Any]")


def definition(*operations):
    group = Group("customers", "CustomersSection", operations=list(operations))
    return ApiDefinition("Api", None, groups=[group])


def test_adds_an_all_method_after_each_paging_operation():
    listing = Operation("list", "GET", "/customers", operation_id="GetCustomers", all_pages=PAGES)
    api = definition(listing, Operation("create", "POST", "/customers"))
    AllPagesMethods().apply(api)
    names = [operation.name for operation in api.groups[0].operations]
    assert names == ["list", "list_all", "create"]
    paged = api.groups[0].operations[1]
    assert (paged.paginate, paged.all_pages, paged.operation_id) == (PAGES, None, "GetCustomers")
    assert (paged.response.expr, paged.response_plain) == ("Customer", "Iterator[dict[str, Any]]")


def test_a_name_clash_names_both_operations():
    listing = Operation("list", "GET", "/customers", operation_id="GetCustomers", all_pages=PAGES)
    clash = Operation("list_all", "GET", "/customers/all", operation_id="GetAllCustomers")
    with pytest.raises(
        ValueError,
        match="customers.list_all: GetCustomers's paginated method clashes with GetAllCustomers",
    ):
        AllPagesMethods().apply(definition(listing, clash))
