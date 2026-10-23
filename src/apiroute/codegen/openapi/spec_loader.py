import json
from pathlib import Path
from typing import Any
from urllib.parse import urljoin, urlsplit

import httpx


class SpecLoader:
    """Loads a JSON or YAML document from a file path or an http(s) URL."""

    def load(self, location: str) -> Any:
        text = self._read(location)
        if location.endswith(".json") or text.lstrip().startswith("{"):
            return json.loads(text)
        return _yaml(text)

    def join(self, base: str, reference: str) -> str:
        """Where a relative $ref points, from the document that contains it."""
        if _is_url(base):
            return urljoin(base, reference)
        return str((Path(base).parent / reference).resolve())

    def _read(self, location: str) -> str:
        if _is_url(location):
            response = httpx.get(location, follow_redirects=True, timeout=30)
            response.raise_for_status()
            return response.text
        return Path(location).read_text()


def _is_url(location: str) -> bool:
    return urlsplit(location).scheme in ("http", "https")


def _yaml(text: str) -> Any:
    # PyYAML comes with the codegen extra and is only needed for YAML specs
    try:
        import yaml
    except ImportError as error:
        raise RuntimeError("YAML specs need PyYAML: pip install apiroute[codegen]") from error
    return yaml.safe_load(text)
