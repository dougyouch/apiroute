from collections.abc import Mapping
from dataclasses import dataclass, field, replace
from typing import Any

from apiroute.base_url_validator import validate_base_url
from apiroute.body_encoder import BODY_FORMATS
from apiroute.query_encoder import QUERY_FORMATS
from apiroute.retries import Retries

# Class attributes a client or section reads its configuration from
CONFIG_ATTRIBUTES = (
    "base_url",
    "headers",
    "query_params",
    "timeout",
    "retries",
    "body_format",
    "query_format",
    "inherit",
)

# These merge down the class hierarchy, as the gem's header and query_param calls do;
# the rest are replaced by a subclass
MERGED_ATTRIBUTES = ("headers", "query_params")

INHERITABLE = frozenset({"headers", "query_params"})


@dataclass(frozen=True)
class ClientConfig:
    base_url: str | None = None
    headers: Mapping[str, Any] = field(default_factory=dict)
    query_params: Mapping[str, Any] = field(default_factory=dict)
    # httpx defaults to 5 seconds, which is short for API calls that do real work
    timeout: float | None = 30.0
    retries: Retries = field(default_factory=Retries)
    body_format: Any = "json"
    query_format: Any = "flat"
    inherit: frozenset[str] = frozenset()

    @classmethod
    def from_class(cls, router_class: type) -> "ClientConfig":
        own = {
            name: vars(router_class)[name]
            for name in CONFIG_ATTRIBUTES
            if name in vars(router_class)
        }
        return _parent_config(router_class)._extended(own, router_class.__qualname__)

    def for_section(self, parent: "ClientConfig", root: "ClientConfig") -> "ClientConfig":
        """This (a section's) config, with its parent's base_url and what it inherits from root."""
        changes: dict[str, Any] = {"base_url": self.base_url or parent.base_url}
        for name in self.inherit:
            changes[name] = {**getattr(root, name), **getattr(self, name)}
        return replace(self, **changes)

    def _extended(self, own: dict[str, Any], owner: str) -> "ClientConfig":
        changes = dict(own)
        for name in MERGED_ATTRIBUTES:
            if name in own:
                changes[name] = _merged_dict(getattr(self, name), own[name])
        if "inherit" in own:
            changes["inherit"] = frozenset(own["inherit"])
        config = replace(self, **changes)
        try:
            config._validate()
        except ValueError as error:
            raise ValueError(f"{owner}: {error}") from error
        return config

    def _validate(self) -> None:
        if self.base_url is not None:
            validate_base_url(self.base_url)
        if not callable(self.body_format) and self.body_format not in BODY_FORMATS:
            raise ValueError(f"body_format must be one of {BODY_FORMATS} or a callable")
        if not callable(self.query_format) and self.query_format not in QUERY_FORMATS:
            raise ValueError(f"query_format must be one of {QUERY_FORMATS} or a callable")
        if not isinstance(self.retries, Retries):
            raise ValueError("retries must be a Retries")
        if not self.inherit <= INHERITABLE:
            raise ValueError(f"inherit may only list {sorted(INHERITABLE)}")


def _parent_config(router_class: type) -> ClientConfig:
    for base in router_class.__mro__[1:]:
        config = vars(base).get("_config")
        if config is not None:
            return config
    return ClientConfig()


def _merged_dict(base: Mapping[str, Any], own: Mapping[str, Any]) -> dict[str, Any]:
    """A None value in the subclass removes that key."""
    merged = {**base, **own}
    return {name: value for name, value in merged.items() if value is not None}
