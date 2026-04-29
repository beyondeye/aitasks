#!/usr/bin/env python3
"""Tests for .aitask-scripts/lib/desync_state.py."""
from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path


PROJECT_DIR = Path(__file__).resolve().parents[1]
HELPER_SRC = PROJECT_DIR / ".aitask-scripts" / "lib" / "desync_state.py"
CHANGELOG_SRC = PROJECT_DIR / ".aitask-scripts" / "aitask_changelog.sh"
LIB_SRC = PROJECT_DIR / ".aitask-scripts" / "lib"


def run(cmd: list[str], cwd: Path, check: bool = True) -> subprocess.CompletedProcess[str]:
    proc = subprocess.run(cmd, cwd=cwd, text=True, capture_output=True, check=False)
    if check and proc.returncode != 0:
        raise AssertionError(
            f"Command failed in {cwd}: {' '.join(cmd)}\nstdout={proc.stdout}\nstderr={proc.stderr}"
        )
    return proc


def git(cwd: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return run(["git", *args], cwd, check=check)


def config_identity(repo: Path) -> None:
    git(repo, "config", "user.email", "test@example.com")
    git(repo, "config", "user.name", "Test")


def copy_helper(project: Path) -> Path:
    helper = project / ".aitask-scripts" / "lib" / "desync_state.py"
    helper.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(HELPER_SRC, helper)
    return helper


def copy_changelog(project: Path) -> Path:
    script_dir = project / ".aitask-scripts"
    lib_dir = script_dir / "lib"
    lib_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(CHANGELOG_SRC, script_dir / "aitask_changelog.sh")
    for name in ["desync_state.py", "task_utils.sh", "terminal_compat.sh", "archive_utils.sh"]:
        shutil.copy2(LIB_SRC / name, lib_dir / name)
    return script_dir / "aitask_changelog.sh"


def make_main_project(root: Path) -> tuple[Path, Path]:
    origin = root / "origin.git"
    project = root / "project"
    git(root, "init", "--bare", "--quiet", str(origin))
    git(root, "clone", "--quiet", str(origin), str(project))
    config_identity(project)
    git(project, "checkout", "-b", "main")
    (project / "README.md").write_text("v1\n", encoding="utf-8")
    git(project, "add", "README.md")
    git(project, "commit", "--quiet", "-m", "initial main")
    git(project, "push", "--quiet", "-u", "origin", "main")
    copy_helper(project)
    return project, origin


def make_local_project_without_remote(root: Path) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    project = root / "project"
    project.mkdir()
    git(project, "init", "--quiet")
    git(project, "checkout", "-b", "main")
    config_identity(project)
    (project / "README.md").write_text("v1\n", encoding="utf-8")
    git(project, "add", "README.md")
    git(project, "commit", "--quiet", "-m", "initial main")
    copy_helper(project)
    return project


def add_data_worktree(project: Path, root: Path) -> Path:
    origin = root / "data-origin.git"
    other = root / "data-other"
    data = project / ".aitask-data"
    git(root, "init", "--bare", "--quiet", str(origin))
    git(root, "clone", "--quiet", str(origin), str(data))
    config_identity(data)
    git(data, "checkout", "-b", "aitask-data")
    (data / "aitasks").mkdir()
    (data / "aitasks" / "t1.md").write_text("one\n", encoding="utf-8")
    git(data, "add", "aitasks/t1.md")
    git(data, "commit", "--quiet", "-m", "initial data")
    git(data, "push", "--quiet", "-u", "origin", "aitask-data")

    git(root, "clone", "--quiet", str(origin), str(other))
    config_identity(other)
    git(other, "checkout", "-b", "aitask-data", "origin/aitask-data")
    (other / "aitasks" / "t2.md").write_text("two\n", encoding="utf-8")
    git(other, "add", "aitasks/t2.md")
    git(other, "commit", "--quiet", "-m", "remote data task")
    git(other, "push", "--quiet", "origin", "aitask-data")
    return data


def helper(project: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return run(["python3", ".aitask-scripts/lib/desync_state.py", *args], project, check=check)


class DesyncStateTests(unittest.TestCase):
    def test_json_lines_and_text_for_remote_ahead_main(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            project, origin = make_main_project(root)
            other = root / "other"
            git(root, "clone", "--quiet", str(origin), str(other))
            config_identity(other)
            git(other, "checkout", "main")
            (other / "remote.txt").write_text("remote\n", encoding="utf-8")
            git(other, "add", "remote.txt")
            git(other, "commit", "--quiet", "-m", "remote main change")
            git(other, "push", "--quiet", "origin", "main")

            data = json.loads(helper(project, "snapshot", "--ref", "main", "--fetch", "--json").stdout)
            ref = data["refs"][0]
            self.assertEqual(ref["name"], "main")
            self.assertEqual(ref["status"], "ok")
            self.assertEqual(ref["ahead"], 0)
            self.assertEqual(ref["behind"], 1)
            self.assertEqual(ref["remote_commits"], ["remote main change"])
            self.assertEqual(ref["remote_changed_paths"], ["remote.txt"])

            lines = helper(project, "snapshot", "--ref", "main", "--format", "lines").stdout
            self.assertIn("REF:main\n", lines)
            self.assertIn("STATUS:ok\n", lines)
            self.assertIn("BEHIND:1\n", lines)
            self.assertIn("REMOTE_COMMIT:remote main change\n", lines)
            self.assertIn("REMOTE_CHANGED_PATH:remote.txt\n", lines)

            text = helper(project, "snapshot", "--ref", "main").stdout.strip()
            self.assertEqual(text, "main: behind 1, ahead 0")

    def test_aitask_data_ref_only_and_missing_worktree(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            project, _ = make_main_project(root)

            missing = json.loads(helper(project, "snapshot", "--ref", "aitask-data", "--json").stdout)
            self.assertEqual(missing["refs"][0]["status"], "missing_worktree")

            add_data_worktree(project, root)
            data = json.loads(
                helper(project, "snapshot", "--ref", "aitask-data", "--fetch", "--format", "json").stdout
            )
            self.assertEqual(len(data["refs"]), 1)
            ref = data["refs"][0]
            self.assertEqual(ref["name"], "aitask-data")
            self.assertEqual(ref["status"], "ok")
            self.assertEqual(ref["behind"], 1)
            self.assertEqual(ref["remote_commits"], ["remote data task"])
            self.assertEqual(ref["remote_changed_paths"], ["aitasks/t2.md"])

    def test_no_remote_missing_local_missing_remote_and_fetch_error(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            no_remote = make_local_project_without_remote(root / "no-remote")
            data = json.loads(helper(no_remote, "snapshot", "--ref", "main", "--json").stdout)
            self.assertEqual(data["refs"][0]["status"], "no_remote")

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            project, _ = make_main_project(root)
            git(project, "checkout", "--detach")
            git(project, "branch", "-D", "main")
            data = json.loads(helper(project, "snapshot", "--ref", "main", "--json").stdout)
            self.assertEqual(data["refs"][0]["status"], "missing_local")

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            origin = root / "origin.git"
            project = root / "project"
            git(root, "init", "--bare", "--quiet", str(origin))
            project.mkdir()
            git(project, "init", "--quiet")
            git(project, "checkout", "-b", "main")
            config_identity(project)
            git(project, "remote", "add", "origin", str(origin))
            (project / "README.md").write_text("v1\n", encoding="utf-8")
            git(project, "add", "README.md")
            git(project, "commit", "--quiet", "-m", "local only")
            copy_helper(project)
            data = json.loads(helper(project, "snapshot", "--ref", "main", "--json").stdout)
            self.assertEqual(data["refs"][0]["status"], "missing_remote")

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            project, _ = make_main_project(root)
            git(project, "remote", "set-url", "origin", f"file://{root}/does-not-exist.git")
            data = json.loads(helper(project, "snapshot", "--ref", "main", "--fetch", "--json").stdout)
            self.assertEqual(data["refs"][0]["status"], "fetch_error")
            self.assertTrue(data["refs"][0]["error"])

    def test_local_ahead_count(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            project, _ = make_main_project(root)
            (project / "local.txt").write_text("local\n", encoding="utf-8")
            git(project, "add", "local.txt")
            git(project, "commit", "--quiet", "-m", "local main change")
            data = json.loads(helper(project, "snapshot", "--ref", "main", "--json").stdout)
            self.assertEqual(data["refs"][0]["status"], "ok")
            self.assertEqual(data["refs"][0]["ahead"], 1)
            self.assertEqual(data["refs"][0]["behind"], 0)

    def test_changelog_warns_for_data_desync_and_ignores_bad_helper_output(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            project, _ = make_main_project(root)
            copy_changelog(project)
            add_data_worktree(project, root)

            git(project, "tag", "v0.0.1")
            (project / "feature.txt").write_text("feature\n", encoding="utf-8")
            git(project, "add", "feature.txt")
            git(project, "commit", "--quiet", "-m", "feature: example (t1)")

            proc = run(["bash", ".aitask-scripts/aitask_changelog.sh", "--gather"], project)
            combined = proc.stdout + proc.stderr
            self.assertIn("Local aitask-data branch is 1 commit(s) behind origin/aitask-data.", combined)

            helper_path = project / ".aitask-scripts" / "lib" / "desync_state.py"
            helper_path.write_text(
                "#!/usr/bin/env python3\nprint('unexpected output')\n",
                encoding="utf-8",
            )
            proc = run(["bash", ".aitask-scripts/aitask_changelog.sh", "--gather"], project)
            combined = proc.stdout + proc.stderr
            self.assertNotIn("Local aitask-data branch is", combined)
            self.assertIn("=== TASK t1 ===", proc.stdout)


if __name__ == "__main__":
    unittest.main()
