from typing import NamedTuple


class OperationFacts(NamedTuple):
    """What pagination rules match an operation on."""

    operation_id: str
    method: str  # upper case
    parameters: frozenset[str]  # wire names
    is_array: bool  # the success response is a JSON array
    properties: frozenset[str]  # the success response object's property names
