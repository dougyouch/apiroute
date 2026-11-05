import json

from apiroute.codegen.diff.api_change import ADDITION, BREAKING, ApiChange


class DiffReport:
    """apiroute diff's output: the changes, and the conventional commit type a client
    repository regenerating with them should use (feat! for breaking changes, feat for
    additions, none when the generated client doesn't change)."""

    def __init__(self, changes: list[ApiChange]):
        self.breaking = [c for c in changes if c.kind == BREAKING]
        self.additions = [c for c in changes if c.kind == ADDITION]

    @property
    def commit_type(self) -> str:
        if self.breaking:
            return "feat!"
        return "feat" if self.additions else "none"

    def text(self) -> str:
        lines = []
        for title, mark, changes in (
            ("Breaking changes", "-", self.breaking),
            ("Additions", "+", self.additions),
        ):
            if changes:
                lines.append(f"{title} ({len(changes)}):")
                lines += [f"  {mark} {change}" for change in changes]
        if not lines:
            lines.append("No changes to the generated client.")
        lines.append(f"Suggested commit type: {self.commit_type}")
        return "\n".join(lines) + "\n"

    def json(self) -> str:
        document = {
            "commit_type": self.commit_type,
            "breaking": [_item(c) for c in self.breaking],
            "additions": [_item(c) for c in self.additions],
        }
        return json.dumps(document, indent=2) + "\n"


def _item(change: ApiChange) -> dict[str, str]:
    return {"subject": change.subject, "detail": change.detail}
