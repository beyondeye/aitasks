"""install.sh's superseded-model prompt on a real terminal (t1910).

check_superseded_model_defaults() asks only when ``[[ -t 0 ]]``, so piping
answers in exercises the report branch and nothing else. This drives the
interactive branch under a PTY (tests/lib/pty_drive.py), with the production
prerequisites loaded in the order install.sh's main() loads them:
``install.sh --source-only``, then ``aitask_setup.sh --source-only`` (which
provides ``resolve_python``), then the function itself.

Run: python3 tests/test_install_superseded_prompt_pty.py
"""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "tests" / "lib"))

try:
    import pty  # noqa: F401
    import pty_drive
except ImportError:  # pragma: no cover - platforms without pty
    pty_drive = None

PROJECT_REL = "aitasks/metadata/codeagent_config.json"
KEPT_NAME = "ait-codeagent-supersession-kept.json"


def _git(cwd, *args):
    return subprocess.run(["git", *args], cwd=str(cwd), check=True,
                          capture_output=True, text=True).stdout.strip()


def make_project(root: Path) -> Path:
    """Legacy-mode project: committed metadata, framework scripts linked in."""
    meta = root / "aitasks" / "metadata"
    meta.mkdir(parents=True)
    (meta / "codeagent_config.json").write_text(json.dumps(
        {"defaults": {"pick": "claudecode/opus5", "qa": "claudecode/haiku4_5"}},
        indent=2) + "\n")
    (meta / "models_claudecode.json").write_text(json.dumps(
        {"models": [{"name": n, "cli_id": n} for n in ("opus5", "opus5_5", "haiku4_5")]},
        indent=2) + "\n")
    # The real scripts (and so the real shipped table), not a copy to drift.
    (root / ".aitask-scripts").symlink_to(REPO_ROOT / ".aitask-scripts")
    (root / ".gitignore").write_text(".aitask-scripts\naitasks/metadata/*.local.json\n")
    _git(root, "init", "-q", ".")
    _git(root, "config", "user.email", "test@test.com")
    _git(root, "config", "user.name", "Test")
    _git(root, "config", "commit.gpgsign", "false")
    _git(root, "add", "-A")
    _git(root, "commit", "-q", "-m", "init")
    return root


def drive_install_check(root: Path, answer: str):
    script = (
        'set -euo pipefail\n'
        f'. "{REPO_ROOT}/install.sh" --source-only\n'
        f'INSTALL_DIR="{root}"\n'
        'EXISTING_INSTALL=true\n'
        'source "$INSTALL_DIR/.aitask-scripts/aitask_setup.sh" --source-only\n'
        'check_superseded_model_defaults\n'
        'echo "FN_RETURNED_0"\n'
    )
    return pty_drive.drive(["bash", "-c", script], [answer], settle=1.0, timeout=120)


@unittest.skipIf(pty_drive is None, "pty module unavailable")
class InstallPromptPtyTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = make_project(Path(self._tmp.name) / "proj")

    def defaults(self):
        return json.loads((self.root / PROJECT_REL).read_text())["defaults"]

    def test_accept_switches_and_commits(self):
        code, transcript = drive_install_check(self.root, "y")
        self.assertEqual(code, 0, transcript)
        self.assertIn("Switch? [Y/n]", transcript)
        self.assertIn("FN_RETURNED_0", transcript)
        self.assertEqual(self.defaults(),
                         {"pick": "claudecode/opus5_5", "qa": "claudecode/haiku4_5"})
        self.assertEqual(_git(self.root, "log", "-1", "--format=%s", "--", PROJECT_REL),
                         "ait: Update codeagent_config.json")
        self.assertEqual(_git(self.root, "status", "--porcelain", "--", PROJECT_REL), "")

    def test_decline_keeps_config_and_remembers(self):
        head = _git(self.root, "rev-parse", "HEAD")
        code, transcript = drive_install_check(self.root, "n")
        self.assertEqual(code, 0, transcript)
        self.assertIn("Switch? [Y/n]", transcript)
        self.assertEqual(self.defaults(),
                         {"pick": "claudecode/opus5", "qa": "claudecode/haiku4_5"})
        self.assertEqual(_git(self.root, "rev-parse", "HEAD"), head)
        kept = json.loads((self.root / ".git" / KEPT_NAME).read_text())
        self.assertEqual(kept, {"project": {"claudecode/opus5": "claudecode/opus5_5"}})


if __name__ == "__main__":
    unittest.main()
