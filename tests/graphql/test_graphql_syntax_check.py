import builtins

import pytest

from apiroute.graphql.graphql_syntax_check import check_syntax


def test_a_syntax_error_is_a_value_error():
    with pytest.raises(ValueError, match="GraphQL syntax error"):
        check_syntax("query A { a(x: ) }")


def test_a_valid_document_passes():
    check_syntax("query A($x: Int) { a(x: $x) }")


def test_does_nothing_without_graphql_core(monkeypatch):
    real_import = builtins.__import__

    def without_graphql(name, *args, **kwargs):
        if name == "graphql" or name.startswith("graphql."):
            raise ImportError(name)
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", without_graphql)
    check_syntax("query A { a(x: ) }")
