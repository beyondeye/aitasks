"""Characterization golden for every model-stats reader (t1912_2).

`tests/lib/stats_reader_capture.py` prints what each reader of
`usagestats` / `verifiedstats` displays: the stats_data rankings, the model
picker, the settings TUI labels and Models tab, and `ait codeagent list-models`.
It runs over the fixture in `tests/golden/stats_readers/`, with "today" pinned.

The golden was captured on the tree **before** t1912_2 routed the readers
through the aitask-stats store overlay. With an empty stats branch, the overlay
must reproduce it byte for byte.

The fixture is writer-consistent: every `verified` prior equals its recorded
`verifiedstats` average, as on the live registry. So this file proves parity
for that shape only. The deliberate `list-models` VERIFIED change for missing
or inconsistent priors is pinned by tests/test_codeagent.sh (Tests 4b / 4c).

Regenerate (only for an intended display change):
  cd <scratch project with the fixture in aitasks/metadata, git-initialised>
  python3 tests/lib/stats_reader_capture.py "$PWD" --write tests/golden/stats_readers/expected.txt

Run: python3 -m pytest tests/test_stats_readers_golden.py -v
"""
from __future__ import annotations

import difflib
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
FIXTURE = REPO_ROOT / "tests" / "golden" / "stats_readers"
EXPECTED = FIXTURE / "expected.txt"
CAPTURE = REPO_ROOT / "tests" / "lib" / "stats_reader_capture.py"
AGENTS = ("claudecode", "codex", "opencode")

GIT_ENV = {
    "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@example.invalid",
    "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@example.invalid",
    "GIT_CONFIG_NOSYSTEM": "1",
}


def _clean_env(extra: dict | None = None) -> dict:
    env = {k: v for k, v in os.environ.items()
           if k not in ("TASK_DIR", "METADATA_DIR", "GIT_DIR", "GIT_WORK_TREE")}
    env.update(GIT_ENV)
    if extra:
        env.update(extra)
    return env


def git(root, *args, env=None) -> str:
    proc = subprocess.run(["git", "-C", str(root), *args], capture_output=True,
                          text=True, env=env or _clean_env(), check=True)
    return proc.stdout.strip()


def make_project(base: Path, name: str = "proj") -> Path:
    """A git-initialised project holding the fixture under aitasks/metadata."""
    root = base / name
    meta = root / "aitasks" / "metadata"
    meta.mkdir(parents=True)
    for agent in AGENTS:
        shutil.copy(FIXTURE / f"models_{agent}.json", meta / f"models_{agent}.json")
    git(root, "init", "-q", "-b", "main")
    return root


def run_capture(root: Path, env: dict | None = None) -> str:
    proc = subprocess.run([sys.executable, str(CAPTURE), str(root)], cwd=root,
                          capture_output=True, text=True, env=env or _clean_env())
    if proc.returncode != 0:
        raise AssertionError(f"capture failed ({proc.returncode}):\n{proc.stderr}")
    return proc.stdout


def diff(expected: str, actual: str) -> str:
    return "".join(difflib.unified_diff(
        expected.splitlines(keepends=True), actual.splitlines(keepends=True),
        "expected.txt", "capture"))


class GoldenParityTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.base = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def test_empty_branch_reproduces_golden(self):
        root = make_project(self.base)
        actual = run_capture(root)
        expected = EXPECTED.read_text(encoding="utf-8")
        self.assertEqual(expected, actual, "reader output drifted:\n" + diff(expected, actual))


if __name__ == "__main__":
    unittest.main()
