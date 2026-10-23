from typing import Any

from apiroute.response_converter import converter_for


class DeferredConverter:
    """Converts with a model type named by a string annotation that couldn't be evaluated
    when the class was created, e.g. `-> "User"` with User defined further down the module.
    The name is looked up on first use."""

    def __init__(self, annotation: str, namespace: dict[str, Any]):
        self._annotation = annotation
        self._namespace = namespace
        self._converter: Any = None
        self._resolved = False

    def convert(self, data: Any) -> Any:
        if not self._resolved:
            model = eval(self._annotation, self._namespace)  # noqa: S307
            self._converter = converter_for(model)
            self._resolved = True
        return data if self._converter is None else self._converter.convert(data)
