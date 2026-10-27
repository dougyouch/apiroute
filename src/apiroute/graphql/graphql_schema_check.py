from typing import Any


def check_against_schema(document: str, schema: Any) -> None:
    """Validates the document against a graphql.GraphQLSchema, raising one ValueError that
    lists every problem with its line and column."""
    from graphql import GraphQLSyntaxError, parse, validate

    try:
        errors = validate(schema, parse(document))
    except GraphQLSyntaxError as error:
        raise ValueError(f"GraphQL syntax error: {error.message}") from error
    if errors:
        problems = "".join(f"\n  - {error.message}{_where(error)}" for error in errors)
        raise ValueError(f"the document doesn't match graphql_schema:{problems}")


def _where(error: Any) -> str:
    locations = error.locations or []
    return "".join(f" (line {spot.line}, column {spot.column})" for spot in locations[:1])
