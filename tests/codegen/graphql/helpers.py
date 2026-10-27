from pathlib import Path

import graphql

SCHEMA = graphql.build_schema(
    (Path(__file__).parents[1] / "fixtures" / "graphql" / "schema.graphql").read_text()
)


def write_operations(directory: Path, files: dict[str, str]) -> str:
    """Writes operation files under directory (relative paths -> text); returns its path."""
    for relative, text in files.items():
        path = directory / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
    return str(directory)
