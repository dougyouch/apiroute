"""GraphQL operations as client methods: the operation is written by hand, the method's
arguments become its variables, and the response's data (or GraphQLError) comes back.

    class GitHub(Client):
        base_url = "https://api.github.com"

        viewer = graphql_route("query Viewer { viewer { login } }", data="viewer")

graphql-core is optional (pip install apiroute[graphql]); when installed, documents are
parsed with it as the class is created, so a syntax error fails early.
"""

from apiroute.graphql.graphql_body import GraphQLBody
from apiroute.graphql.graphql_decoder import GraphQLDecoder
from apiroute.graphql.graphql_document import GraphQLDocument
from apiroute.graphql.graphql_error import GraphQLError
from apiroute.graphql.graphql_route import graphql_route

__all__ = ["GraphQLBody", "GraphQLDecoder", "GraphQLDocument", "GraphQLError", "graphql_route"]
