from apiroute.codegen.import_order import import_names


def test_constants_then_classes_then_functions_case_insensitively():
    names = ["route", "Query", "TYPE_CHECKING", "lazy", "Client", "AbcList", "Abcd"]
    assert import_names(names) == "TYPE_CHECKING, Abcd, AbcList, Client, Query, lazy, route"
