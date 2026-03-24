"""Tests for codebrowser/history_data.py module.

Run: python3 -m pytest tests/test_history_data.py -v

Uses temporary git repos with controlled commits to test all functions.
"""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

# Add codebrowser, board, and lib to path
_scripts = Path(__file__).resolve().parents[1] / ".aitask-scripts"
sys.path.insert(0, str(_scripts / "codebrowser"))
sys.path.insert(0, str(_scripts / "board"))
sys.path.insert(0, str(_scripts / "lib"))

from history_data import (
    CompletedTask,
    PlatformInfo,
    TaskCommitInfo,
    detect_platform_info,
    find_child_tasks,
    find_commits_for_task,
    find_sibling_tasks,
    load_completed_tasks_chunk,
    load_plan_content,
    load_task_content,
    load_task_index,
)


def _git(cwd, *args):
    """Run git command in the given directory."""
    result = subprocess.run(
        ["git"] + list(args),
        capture_output=True,
        text=True,
        cwd=cwd,
    )
    if result.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} failed: {result.stderr}")
    return result.stdout.strip()


def _make_task_file(path: Path, **frontmatter):
    """Write a task file with YAML frontmatter."""
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = ["---"]
    for k, v in frontmatter.items():
        if isinstance(v, list):
            lines.append(f"{k}: [{', '.join(v)}]")
        else:
            lines.append(f"{k}: {v}")
    lines.append("---")
    lines.append("Task body content.")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


class GitRepoTestBase(unittest.TestCase):
    """Base class that creates a temporary git repo with task fixtures."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)

        # Initialize git repo
        _git(self.root, "init")
        _git(self.root, "config", "user.email", "test@test.com")
        _git(self.root, "config", "user.name", "Test")

        # Create directory structure
        archived = self.root / "aitasks" / "archived"
        archived.mkdir(parents=True)
        plans_archived = self.root / "aiplans" / "archived"
        plans_archived.mkdir(parents=True)

        # Create archived task files
        _make_task_file(
            archived / "t42_implement_auth.md",
            status="Done",
            priority="high",
            effort="medium",
            issue_type="feature",
            labels=["backend", "auth"],
            completed_at="2026-03-20 10:00",
        )
        _make_task_file(
            archived / "t43_fix_login.md",
            status="Done",
            priority="medium",
            effort="low",
            issue_type="bug",
            labels=["frontend"],
            completed_at="2026-03-19 09:00",
        )

        # Create child task
        child_dir = archived / "t10"
        child_dir.mkdir()
        _make_task_file(
            child_dir / "t10_1_add_tests.md",
            status="Done",
            priority="low",
            effort="low",
            issue_type="test",
            labels=["testing"],
            completed_at="2026-03-18 08:00",
        )
        _make_task_file(
            child_dir / "t10_2_add_docs.md",
            status="Done",
            priority="low",
            effort="low",
            issue_type="documentation",
            labels=["docs"],
            completed_at="2026-03-17 08:00",
        )
        _make_task_file(
            child_dir / "t10_3_cleanup.md",
            status="Done",
            priority="low",
            effort="low",
            issue_type="chore",
            labels=["cleanup"],
            completed_at="2026-03-16 08:00",
        )

        # Create plan file
        plan_dir = plans_archived / "p10"
        plan_dir.mkdir()
        (plans_archived / "p42_implement_auth.md").write_text(
            "# Plan for t42\n\nImplementation details.\n"
        )
        (plan_dir / "p10_1_add_tests.md").write_text(
            "# Plan for t10_1\n\nTest implementation.\n"
        )

        # Initial commit with all files
        (self.root / "src").mkdir()
        (self.root / "src" / "auth.py").write_text("# auth module\n")
        (self.root / "src" / "login.py").write_text("# login module\n")
        _git(self.root, "add", "-A")
        _git(self.root, "commit", "-m", "initial commit")

        # Create commits with task references
        (self.root / "src" / "auth.py").write_text("# auth module v2\ndef auth(): pass\n")
        _git(self.root, "add", "src/auth.py")
        _git(self.root, "commit", "-m", "feature: Add auth module (t42)")

        (self.root / "src" / "login.py").write_text("# login fix\ndef login(): pass\n")
        _git(self.root, "add", "src/login.py")
        _git(self.root, "commit", "-m", "bug: Fix login validation (t43)")

        (self.root / "src" / "auth.py").write_text(
            "# auth module v3\ndef auth(): pass\ndef verify(): pass\n"
        )
        _git(self.root, "add", "src/auth.py")
        _git(self.root, "commit", "-m", "feature: Add auth verification (t42)")

        (self.root / "src" / "test_auth.py").write_text("# tests\n")
        _git(self.root, "add", "src/test_auth.py")
        _git(self.root, "commit", "-m", "test: Add auth tests (t10_1)")

    def tearDown(self):
        self.tmp.cleanup()


class TestLoadTaskIndex(GitRepoTestBase):
    def test_returns_sorted_by_date_desc(self):
        index = load_task_index(self.root)
        dates = [t.commit_date for t in index]
        self.assertEqual(dates, sorted(dates, reverse=True))

    def test_deduplicates_commits(self):
        # t42 has 2 commits, should only appear once with most recent
        index = load_task_index(self.root)
        t42_entries = [t for t in index if t.task_id == "42"]
        self.assertEqual(len(t42_entries), 1)

    def test_merges_metadata(self):
        index = load_task_index(self.root)
        t42 = next((t for t in index if t.task_id == "42"), None)
        self.assertIsNotNone(t42)
        self.assertEqual(t42.issue_type, "feature")
        self.assertEqual(t42.priority, "high")
        self.assertEqual(t42.name, "implement_auth")

    def test_skips_no_metadata(self):
        # Create a commit referencing a task not in the archive
        (self.root / "src" / "new.py").write_text("# new\n")
        _git(self.root, "add", "src/new.py")
        _git(self.root, "commit", "-m", "feature: Something (t999)")
        index = load_task_index(self.root)
        t999 = [t for t in index if t.task_id == "999"]
        self.assertEqual(len(t999), 0)

    def test_empty_repo(self):
        tmp2 = tempfile.TemporaryDirectory()
        root2 = Path(tmp2.name)
        _git(root2, "init")
        _git(root2, "config", "user.email", "test@test.com")
        _git(root2, "config", "user.name", "Test")
        (root2 / "dummy.txt").write_text("init")
        _git(root2, "add", "dummy.txt")
        _git(root2, "commit", "-m", "init")
        (root2 / "aitasks" / "archived").mkdir(parents=True)
        index = load_task_index(root2)
        self.assertEqual(index, [])
        tmp2.cleanup()


class TestLoadTaskContent(GitRepoTestBase):
    def test_loose_parent(self):
        content = load_task_content(self.root, "42")
        self.assertIsNotNone(content)
        self.assertIn("issue_type: feature", content)

    def test_loose_child(self):
        content = load_task_content(self.root, "10_1")
        self.assertIsNotNone(content)
        self.assertIn("issue_type: test", content)

    def test_not_found(self):
        content = load_task_content(self.root, "999")
        self.assertIsNone(content)


class TestLoadPlanContent(GitRepoTestBase):
    def test_found_parent(self):
        content = load_plan_content(self.root, "42")
        self.assertIsNotNone(content)
        self.assertIn("Plan for t42", content)

    def test_found_child(self):
        content = load_plan_content(self.root, "10_1")
        self.assertIsNotNone(content)
        self.assertIn("Plan for t10_1", content)

    def test_not_found(self):
        content = load_plan_content(self.root, "999")
        self.assertIsNone(content)


class TestLoadCompletedTasksChunk(unittest.TestCase):
    def _make_index(self, n: int) -> list:
        return [
            CompletedTask(
                task_id=str(i),
                name=f"task_{i}",
                issue_type="feature",
                labels=[],
                priority="medium",
                effort="medium",
                commit_date=f"2026-03-{i:02d}T10:00:00",
                commit_hash=f"abc{i:04d}",
                file_source="loose",
                metadata={},
            )
            for i in range(1, n + 1)
        ]

    def test_first_page(self):
        index = self._make_index(15)
        chunk, has_more = load_completed_tasks_chunk(index, 0, 10)
        self.assertEqual(len(chunk), 10)
        self.assertTrue(has_more)

    def test_last_page(self):
        index = self._make_index(15)
        chunk, has_more = load_completed_tasks_chunk(index, 10, 10)
        self.assertEqual(len(chunk), 5)
        self.assertFalse(has_more)

    def test_empty_index(self):
        chunk, has_more = load_completed_tasks_chunk([], 0, 10)
        self.assertEqual(chunk, [])
        self.assertFalse(has_more)


class TestFindCommitsForTask(GitRepoTestBase):
    def test_returns_all_commits(self):
        commits = find_commits_for_task("42", self.root)
        self.assertEqual(len(commits), 2)

    def test_affected_files(self):
        commits = find_commits_for_task("42", self.root)
        all_files = set()
        for c in commits:
            all_files.update(c.affected_files)
        self.assertIn("src/auth.py", all_files)

    def test_no_match(self):
        commits = find_commits_for_task("999", self.root)
        self.assertEqual(len(commits), 0)


class TestFindChildAndSiblingTasks(unittest.TestCase):
    def setUp(self):
        self.index = [
            CompletedTask(
                task_id="10_1",
                name="add_tests",
                issue_type="test",
                labels=[],
                priority="low",
                effort="low",
                commit_date="2026-03-18",
                commit_hash="aaa",
                file_source="loose",
                metadata={},
            ),
            CompletedTask(
                task_id="10_2",
                name="add_docs",
                issue_type="doc",
                labels=[],
                priority="low",
                effort="low",
                commit_date="2026-03-17",
                commit_hash="bbb",
                file_source="loose",
                metadata={},
            ),
            CompletedTask(
                task_id="10_3",
                name="cleanup",
                issue_type="chore",
                labels=[],
                priority="low",
                effort="low",
                commit_date="2026-03-16",
                commit_hash="ccc",
                file_source="loose",
                metadata={},
            ),
            CompletedTask(
                task_id="11_1",
                name="other",
                issue_type="feature",
                labels=[],
                priority="low",
                effort="low",
                commit_date="2026-03-15",
                commit_hash="ddd",
                file_source="loose",
                metadata={},
            ),
        ]

    def test_find_child_tasks(self):
        children = find_child_tasks("10", self.index)
        ids = [c.task_id for c in children]
        self.assertEqual(sorted(ids), ["10_1", "10_2", "10_3"])

    def test_find_sibling_tasks_excludes_self(self):
        siblings = find_sibling_tasks("10_2", self.index)
        ids = [s.task_id for s in siblings]
        self.assertIn("10_1", ids)
        self.assertIn("10_3", ids)
        self.assertNotIn("10_2", ids)

    def test_find_sibling_tasks_parent_returns_empty(self):
        siblings = find_sibling_tasks("10", self.index)
        self.assertEqual(siblings, [])


class TestDetectPlatformInfo(unittest.TestCase):
    def _make_repo_with_remote(self, url: str) -> tuple:
        tmp = tempfile.TemporaryDirectory()
        root = Path(tmp.name)
        _git(root, "init")
        _git(root, "config", "user.email", "test@test.com")
        _git(root, "config", "user.name", "Test")
        (root / "dummy.txt").write_text("init")
        _git(root, "add", "dummy.txt")
        _git(root, "commit", "-m", "init")
        _git(root, "remote", "add", "origin", url)
        return root, tmp

    def test_github_https(self):
        root, tmp = self._make_repo_with_remote(
            "https://github.com/user/repo.git"
        )
        info = detect_platform_info(root)
        self.assertIsNotNone(info)
        self.assertEqual(info.platform, "github")
        self.assertIn("github.com/user/repo/commit/{hash}", info.commit_url_template)
        tmp.cleanup()

    def test_github_ssh(self):
        root, tmp = self._make_repo_with_remote("git@github.com:user/repo.git")
        info = detect_platform_info(root)
        self.assertIsNotNone(info)
        self.assertEqual(info.platform, "github")
        self.assertEqual(info.base_url, "https://github.com/user/repo")
        tmp.cleanup()

    def test_gitlab(self):
        root, tmp = self._make_repo_with_remote(
            "https://gitlab.com/org/project.git"
        )
        info = detect_platform_info(root)
        self.assertIsNotNone(info)
        self.assertEqual(info.platform, "gitlab")
        self.assertIn("/-/commit/{hash}", info.commit_url_template)
        tmp.cleanup()

    def test_bitbucket(self):
        root, tmp = self._make_repo_with_remote(
            "git@bitbucket.org:team/repo.git"
        )
        info = detect_platform_info(root)
        self.assertIsNotNone(info)
        self.assertEqual(info.platform, "bitbucket")
        self.assertIn("/commits/{hash}", info.commit_url_template)
        tmp.cleanup()

    def test_unknown_host(self):
        root, tmp = self._make_repo_with_remote(
            "https://gitea.example.com/user/repo.git"
        )
        info = detect_platform_info(root)
        self.assertIsNone(info)
        tmp.cleanup()


if __name__ == "__main__":
    unittest.main()
