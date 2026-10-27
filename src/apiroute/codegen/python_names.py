import keyword
import re

# Attributes every generated client or section already has
RESERVED = frozenset(
    {
        "aio",
        "with_options",
        "models",
        "should_retry",
        "escape_path",
        "on_request",
        "on_response",
        "last_response",
        "base_url",
        "headers",
        "query_params",
        "timeout",
        "retries",
        "body_format",
        "query_format",
        "inherit",
        "compile_routes",
    }
)

# Names a pydantic field can't take without shadowing BaseModel
MODEL_RESERVED = frozenset(
    {
        "copy",
        "dict",
        "json",
        "schema",
        "schema_json",
        "validate",
        "construct",
        "from_orm",
        "parse_obj",
        "parse_raw",
        "parse_file",
        "update_forward_refs",
        "model_config",
        "model_fields",
        "model_computed_fields",
        "model_extra",
        "model_fields_set",
    }
)

# Python 3.12's soft keywords, fixed rather than read from the running Python (3.10 and 3.11
# don't list "type"), so the same spec gives the same code whichever Python generates it
SOFT_KEYWORDS = frozenset({"_", "case", "match", "type"})

_WORDS = re.compile(r"[A-Z]+(?=[A-Z][a-z0-9])|[A-Z]?[a-z0-9]+|[A-Z]+|[0-9]+")


def words(text: str) -> list[str]:
    """getRepoByID / get-repo_by id -> ["get", "Repo", "By", "ID"]"""
    return _WORDS.findall(text)


def snake_case(text: str) -> str:
    name = "_".join(word.lower() for word in words(text)) or "value"
    return safe_identifier(name)


def pascal_case(text: str) -> str:
    name = "".join(word[:1].upper() + word[1:] for word in words(text)) or "Model"
    return safe_identifier(name)


def safe_identifier(name: str) -> str:
    """A name Python accepts: digits can't lead, and keywords take a trailing underscore."""
    if name[0].isdigit():
        name = f"n{name}"
    if keyword.iskeyword(name) or name in SOFT_KEYWORDS:
        name = f"{name}_"
    return name


def unique(name: str, taken: set[str], reserved: frozenset[str] = RESERVED) -> str:
    """name, or name_2, name_3 ... when it is taken or reserved; records the result."""
    candidate, number = name, 1
    while candidate in taken or candidate in reserved:
        number += 1
        candidate = f"{name}_{number}"
    taken.add(candidate)
    return candidate
