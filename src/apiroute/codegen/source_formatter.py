import json
import shutil
import subprocess
from collections.abc import Iterable
from pathlib import Path


class SourceFormatter:
    """Runs ruff over generated files when it's installed: import sorting (`ruff check
    --select I --fix`) then `ruff format`, so long lines and imports match ruff's style.
    --isolated ignores the surrounding project's ruff settings, keeping output reproducible.
    isort is told what a consuming project's own settings would say: apiroute is third-party,
    and `first_party` (a --base-class module's package) is the project's own.
    Without ruff the files stay as the emitter wrote them: valid, with some long lines."""

    def format(
        self, paths: list[Path], line_length: int = 100, first_party: Iterable[str] = ()
    ) -> bool:
        ruff = shutil.which("ruff")
        if ruff is None or not paths:
            return False
        files = [str(path) for path in paths]
        options = ["--isolated", "--quiet", f"--line-length={line_length}"]
        sort = [ruff, "check", *options, *_isort_sections(first_party), "--select=I", "--fix"]
        sort += ["--exit-zero", *files]
        if subprocess.run(sort, check=False).returncode != 0:
            return False
        return subprocess.run([ruff, "format", *options, *files], check=False).returncode == 0


def _isort_sections(first_party: Iterable[str]) -> list[str]:
    options = ["--config", 'lint.isort.known-third-party = ["apiroute"]']
    known = sorted(set(first_party))
    if known:
        options += ["--config", f"lint.isort.known-first-party = {json.dumps(known)}"]
    return options
