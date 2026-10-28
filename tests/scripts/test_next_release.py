import subprocess
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).parents[2] / "scripts" / "next_release.py"


@pytest.fixture
def repo(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _git("init", "-q", "-b", "main")
    _git("config", "user.name", "Test")
    _git("config", "user.email", "test@example.test")
    return tmp_path


def _git(*arguments):
    subprocess.run(["git", *arguments], check=True, capture_output=True)


def commit(message):
    _git("commit", "-q", "--allow-empty", "-m", message)


def release(*options):
    result = subprocess.run(
        [sys.executable, str(SCRIPT), *options], check=True, capture_output=True, text=True
    )
    return result.stdout.strip()


def test_the_first_release_is_0_1_0(repo):
    commit("feat: start")
    assert release() == "0.1.0"


@pytest.mark.parametrize(
    ("messages", "version"),
    [
        (["docs: typo"], "1.2.4"),
        (["chore: tidy", "fix: a bug"], "1.2.4"),
        (["fix: a bug", "feat: a feature"], "1.3.0"),
        (["feat(codegen): a feature"], "1.3.0"),
        (["feat!: a breaking feature"], "2.0.0"),
        (["fix(api)!: a breaking fix"], "2.0.0"),
        (["refactor: rename", "fix: x\n\nBREAKING CHANGE: Client.get is gone"], "2.0.0"),
    ],
)
def test_the_bump_follows_the_commits_since_the_last_tag(repo, messages, version):
    commit("feat: before")
    _git("tag", "v1.2.3")
    for message in messages:
        commit(message)
    assert release() == version


def test_a_tagged_head_repeats_its_release(repo):
    commit("feat: one")
    _git("tag", "v1.0.0")
    commit("feat: two")
    _git("tag", "v1.1.0")
    assert release() == "1.1.0"
    assert "feat: two" in release("--notes") and "feat: one" not in release("--notes")


def test_other_tags_are_ignored(repo):
    commit("feat: one")
    _git("tag", "v1.0.0")
    _git("tag", "nightly")
    commit("fix: two")
    _git("tag", "v9.9.9-rc1")
    assert release() == "1.0.1"


def test_notes_group_the_commits(repo):
    commit("chore: before")
    _git("tag", "v1.0.0")
    for message in ["feat: add x", "fix: mend y", "docs: explain z", "feat!: drop w"]:
        commit(message)
    notes = release("--notes")
    assert notes.index("### Breaking changes") < notes.index("### Features")
    assert notes.index("### Fixes") < notes.index("### Other changes")
    assert "- feat: add x (" in notes and "- docs: explain z (" in notes
    assert notes.count("feat!: drop w") == 2  # under breaking changes and under features
