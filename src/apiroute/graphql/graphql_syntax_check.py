def check_syntax(document: str) -> None:
    """Parses the document with graphql-core when it is installed (the graphql extra), raising
    ValueError on a syntax error; without it, does nothing."""
    try:
        from graphql import GraphQLSyntaxError, parse
    except ImportError:
        return
    try:
        parse(document)
    except GraphQLSyntaxError as error:
        raise ValueError(f"GraphQL syntax error: {error.message}") from error
