"""Tests for the link-relevance history replay harness (t1768).

`website/check_link_relevance_history.py` replays the detector's `scan()` over
every commit touching `website/content`. Every test here drives it at a
**throwaway git repository** built in a temporary directory -- never at this
repository's own history, which a rewrite or a shallow clone can take away.

No test changes the process working directory: every git call passes `cwd=`.

Run: bash tests/run_all_python_tests.sh
  or: python3 -m pytest tests/test_check_link_relevance_history.py -v
"""
import io
import os
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "website"))

import check_link_relevance as clr  # noqa: E402
import check_link_relevance_history as hist  # noqa: E402

# Variables that would point every git call -- the fixture's and the harness's --
# at some other repository. Scrubbed for the duration of each test.
GIT_LOCATION_VARS = ("GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE",
                     "GIT_OBJECT_DIRECTORY", "GIT_COMMON_DIR")

TARGET = "# Target\n\nUnrelated prose.\n\n## Sec\n\nNothing here either.\n"
LINK = '[`ait demo`]({{< relref "/docs/target" >}})\n'


class Repo:
    """A throwaway repository with a `website/content` tree."""

    def __init__(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self._env = {
            **os.environ,
            # Keep the host's global config (signing, hooks, templates) out.
            "GIT_CONFIG_GLOBAL": os.devnull,
            "GIT_CONFIG_NOSYSTEM": "1",
            "GIT_AUTHOR_NAME": "fixture", "GIT_AUTHOR_EMAIL": "f@example.invalid",
            "GIT_COMMITTER_NAME": "fixture",
            "GIT_COMMITTER_EMAIL": "f@example.invalid",
        }
        self.git("init", "-q")

    def git(self, *args) -> str:
        return subprocess.run(["git", *args], cwd=self.root, env=self._env,
                              capture_output=True, text=True,
                              check=True).stdout.strip()

    def page(self, rel: str, body: str) -> Path:
        path = self.root / "website" / "content" / (rel + ".md")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(body)
        return path

    def commit(self, message: str) -> str:
        self.git("add", "-A")
        self.git("commit", "-q", "-m", message)
        return self.git("rev-parse", "HEAD")

    def close(self):
        self._tmp.cleanup()


class HistoryTestCase(unittest.TestCase):
    def setUp(self):
        env = patch.dict(os.environ)
        env.start()
        self.addCleanup(env.stop)
        for var in GIT_LOCATION_VARS:
            os.environ.pop(var, None)
        self.repo = Repo()
        self.addCleanup(self.repo.close)

    def run_main(self, *args):
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            rc = hist.main(["--repo", str(self.repo.root), *args])
        return rc, out.getvalue(), err.getvalue()

    def rows(self):
        return hist.replay(self.repo.root, "HEAD").rows


class LegacyTreeTests(HistoryTestCase):
    """The case a CLI-based replay lost: a tree older than the corpus controls."""

    def test_legacy_tree_still_contributes_its_record(self):
        self.repo.page("docs/target", TARGET)
        self.repo.page("docs/src", LINK)
        self.repo.commit("legacy tree")

        # Assert the fixture has the shape it claims: none of the pages the
        # corpus controls key on exist, so the CLI would fail every one of them.
        content = self.repo.root / "website" / "content"
        corpus = clr.evaluate_controls(clr.scan(content), clr.CORPUS_CONTROLS)
        self.assertTrue(corpus)
        self.assertFalse(any(corpus.values()), corpus)

        key = ("docs/src.md", "ait demo", "/docs/target/", "page")
        self.assertIn(key, self.rows())

        rc, out, err = self.run_main()
        self.assertEqual(rc, 0, err)
        self.assertIn("`ait demo`  ->  /docs/target/ [page]", out)
        self.assertIn("NOT APPLICABLE to historical trees", out)
        for name, _ in clr.CORPUS_CONTROLS:
            self.assertIn(name, out)


class AggregationTests(HistoryTestCase):

    def test_a_repointed_link_is_counted_in_the_sweeps_it_missed(self):
        self.repo.page("docs/target", TARGET)
        self.repo.page("docs/demo", "# Demo\n\nRun `ait demo` here.\n")
        self.repo.page("docs/src", LINK)
        broken = self.repo.commit("link points at the wrong page")
        self.repo.page("docs/src", '[`ait demo`]({{< relref "/docs/demo" >}})\n')
        self.repo.commit("link repointed")

        result = hist.replay(self.repo.root, "HEAD")
        # An empty aggregation reads exactly like "no records in history".
        self.assertEqual(len(result.rows), 1, result.rows)
        self.assertEqual(result.swept, 2)
        row = result.rows[("docs/src.md", "ait demo", "/docs/target/", "page")]
        self.assertEqual(row.sweeps, 1)
        self.assertEqual((row.newest, row.oldest), (broken[:9], broken[:9]))

    def test_scope_is_part_of_the_record_identity(self):
        """Page-scoped and anchored are different cases under the classifier."""
        self.repo.page("docs/target", TARGET)
        self.repo.page("docs/src", LINK)
        self.repo.commit("page-scoped")
        self.repo.page(
            "docs/src", '[`ait demo`]({{< relref "/docs/target" >}}#sec)\n')
        self.repo.commit("anchored")

        rows = self.rows()
        self.assertIn(("docs/src.md", "ait demo", "/docs/target/", "page"), rows)
        self.assertIn(("docs/src.md", "ait demo", "/docs/target/", "#sec"), rows)
        self.assertEqual(len(rows), 2)

    def test_a_commit_without_website_content_is_skipped_not_fatal(self):
        self.repo.page("docs/target", TARGET)
        self.repo.page("docs/src", LINK)
        self.repo.commit("content")
        self.repo.git("rm", "-r", "-q", "website")
        self.repo.commit("content removed")

        result = hist.replay(self.repo.root, "HEAD")
        self.assertEqual((result.swept, result.skipped), (1, 1))
        self.assertEqual(len(result.rows), 1)

    def _delete_object(self, spec: str) -> str:
        """Remove one loose object -- what a partial or corrupt clone looks like."""
        sha = self.repo.git("rev-parse", spec)
        path = self.repo.root / ".git" / "objects" / sha[:2] / sha[2:]
        self.assertTrue(path.exists(), f"{spec} is not a loose object")
        path.chmod(0o644)
        path.unlink()
        return sha

    def test_an_archive_failure_fails_the_run_instead_of_counting_a_skip(self):
        self.repo.page("docs/target", TARGET)
        self.repo.page("docs/src", LINK)
        self.repo.commit("content")
        self._delete_object("HEAD:website/content/docs/src.md")

        # Assert the fixture has the shape it claims: the directory is still
        # visible in the tree, and `git archive` genuinely fails on it.
        listed = subprocess.run(["git", "ls-tree", "HEAD", "--", "website/content"],
                                cwd=self.repo.root, capture_output=True, text=True)
        self.assertEqual(listed.returncode, 0)
        self.assertIn("website/content", listed.stdout)
        archive = subprocess.run(["git", "archive", "HEAD", "website/content"],
                                 cwd=self.repo.root, capture_output=True)
        self.assertNotEqual(archive.returncode, 0)

        with self.assertRaises(hist.ReplayError):
            hist.replay(self.repo.root, "HEAD")
        rc, out, err = self.run_main()
        self.assertEqual(rc, 1)
        self.assertIn("REPLAY FAILED", err)
        self.assertNotIn("skipped (no website/content)", out)

    def test_an_unreadable_tree_is_an_error_not_an_absence(self):
        """The ls-tree probe itself failing must not read as "no content"."""
        self.repo.page("docs/target", TARGET)
        self.repo.commit("content")
        self._delete_object("HEAD:website")
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(hist.ReplayError):
                hist._extract(self.repo.root, "HEAD", Path(tmp))

    def test_the_subject_label_is_carried_into_the_table(self):
        self.repo.page("docs/commands/lock", "# Lock\n\nAtomic.\n")
        self.repo.page(
            "docs/src", '[`aitask_lock.sh`]({{< relref "/docs/commands/lock" >}})\n')
        self.repo.commit("subject-of-page")

        row = self.rows()[("docs/src.md", "aitask_lock.sh",
                           "/docs/commands/lock/", "page")]
        self.assertTrue(row.subject)
        _, out, _ = self.run_main()
        self.assertIn("[page]  [subject-of-page]", out)


class ControlTests(HistoryTestCase):

    def setUp(self):
        super().setUp()
        self.repo.page("docs/target", TARGET)
        self.repo.page("docs/src", LINK)
        self.repo.commit("content")

    def test_an_engine_control_failure_fails_the_run(self):
        with patch.object(clr, "_probe_scope_narrowing", lambda: False):
            rc, out, err = self.run_main()
        self.assertEqual(rc, 1)
        self.assertIn("anchor scoping narrowed the check: False", out)
        self.assertIn("FAILED CONTROL", err)

    def test_head_control_passes_on_a_clean_tree(self):
        rc, out, _ = self.run_main()
        self.assertEqual(rc, 0)
        self.assertIn("head ctl      : PASSED", out)

    def test_head_control_skips_on_a_modified_page(self):
        self.repo.page("docs/src", LINK + '[`ait other`]({{< relref "/docs/target" >}})\n')
        rc, out, _ = self.run_main()
        self.assertEqual(rc, 0)
        self.assertIn("head ctl      : SKIPPED", out)
        self.assertIn("website/content/docs/src.md", out)

    def test_head_control_skips_on_an_untracked_page(self):
        """Not passes, and not fails.

        The untracked page adds a record the archived HEAD cannot have, so a
        guard that used `git diff` (blind to untracked files) would run the
        comparison and report FAILED here.
        """
        self.repo.page("docs/new", '[`ait new`]({{< relref "/docs/target" >}})\n')
        rc, out, _ = self.run_main()
        self.assertEqual(rc, 0)
        self.assertIn("head ctl      : SKIPPED", out)
        self.assertIn("website/content/docs/new.md", out)
        self.assertNotIn("FAILED", out)

    def test_head_control_fails_when_replay_and_live_disagree(self):
        """The control can fail: break extraction and it must say so."""
        with patch.object(hist, "_extract", lambda repo, rev, dest: None):
            verdict, _ = hist.head_control(self.repo.root)
        self.assertEqual(verdict, "failed")


class UsageTests(unittest.TestCase):

    def test_a_non_repository_is_a_usage_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            with patch.dict(os.environ, {"GIT_CEILING_DIRECTORIES": tmp}):
                for var in GIT_LOCATION_VARS:
                    os.environ.pop(var, None)
                err = io.StringIO()
                with redirect_stdout(io.StringIO()), redirect_stderr(err):
                    rc = hist.main(["--repo", tmp])
        self.assertEqual(rc, 2)
        self.assertIn("not a git repository", err.getvalue())


if __name__ == "__main__":
    unittest.main()
