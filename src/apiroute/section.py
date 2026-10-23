from typing import Any

from apiroute.client_config import ClientConfig
from apiroute.router import Router


class Section(Router):
    """A group of routes nested in a client class, reached as client.<class name>.

    It uses its parent's base_url unless it sets one, and only the settings named in
    `inherit` ("headers", "query_params") from the root client. {name} placeholders and
    callable headers resolve against the root client.
    """

    _is_section = True

    def __init__(self, parent: Router):
        self._parent = parent

    @property
    def _root(self) -> Any:
        return self._parent._root

    def _request_config(self) -> ClientConfig:
        return type(self)._config.for_section(
            self._parent._request_config(), type(self._root)._config
        )
