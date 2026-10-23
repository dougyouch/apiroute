from typing import Any


class PydanticConverter:
    """Validates a response with pydantic's TypeAdapter: models, dataclasses and any type
    pydantic understands, with its coercion and error messages."""

    def __init__(self, model: Any):
        # pydantic is optional; this class is only built when the model type uses it
        from pydantic import TypeAdapter

        self._adapter = TypeAdapter(model)

    def convert(self, data: Any) -> Any:
        return self._adapter.validate_python(data)
