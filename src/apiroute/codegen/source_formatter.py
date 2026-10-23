import shutil
import subprocess
from pathlib import Path


class SourceFormatter:
    """Runs ruff over generated files when it's installed: import sorting (`ruff check
    --select I --fix`) then `ruff format`, so long lines and imports match ruff's style.
    --isolated ignores the surrounding project's ruff settings, keeping output reproducible.
    Without ruff the files stay as the emitter wrote them: valid, with some long lines."""

    def format(self, paths: list[Path], line_length: int = 100) -> bool:
        ruff = shutil.which("ruff")
        if ruff is None or not paths:
            return False
        files = [str(path) for path in paths]
        options = ["--isolated", "--quiet", f"--line-length={line_length}"]
        sort = [ruff, "check", *options, "--select=I", "--fix", "--exit-zero", *files]
        if subprocess.run(sort, check=False).returncode != 0:
            return False
        return subprocess.run([ruff, "format", *options, *files], check=False).returncode == 0
