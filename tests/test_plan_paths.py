"""Tests for lib/plan_paths.py — the shared plan-path extractor (t1569_1).

These pin what the drift check's own suite CANNOT observe. That suite exercises
the extractor through `OVERLAP:` lines, and the intersect there is `grep -Fxf`,
which emits in the remote list's order — so the plan-side collation is invisible
at that boundary. It is pinned here instead, against the module directly.
"""
from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = REPO_ROOT / ".aitask-scripts"
sys.path.insert(0, str(SCRIPTS_DIR / "lib"))

import plan_paths  # noqa: E402


class ExtractionTests(unittest.TestCase):
    def test_strips_dot_slash_and_dedupes(self):
        text = "./a/b.sh and a/b.sh again and ./a/b.sh"
        self.assertEqual(plan_paths.extract(text), ["a/b.sh"])

    def test_extension_allowlist_is_the_known_narrowing(self):
        """A Go/Rust/JS plan yields NOTHING. This is the recall limit that makes
        an empty result mean 'not measured', never 'nothing to worry about'."""
        text = "internal/pkg/server.go src/main.rs app/index.ts style.css"
        self.assertEqual(plan_paths.extract(text), [])

    def test_every_allowlisted_extension_is_reachable(self):
        text = " ".join(f"d/f.{e}" for e in plan_paths._EXTENSIONS)
        got = plan_paths.extract(text)
        self.assertEqual(len(got), len(plan_paths._EXTENSIONS))

    def test_leading_hyphen_token_is_produced_the_way_the_corpus_makes_one(self):
        """`SKILL-${p}-claude.md` splits on `$`/`{`, yielding `-claude.md` —
        exactly how the three live-corpus tokens arise."""
        self.assertIn("-claude.md", plan_paths.extract("SKILL-${p}-claude.md"))

    def test_colon_and_newline_can_never_appear_in_a_token(self):
        """Pins the reachability limit recorded in the module docstring: the
        `malformed` class may only grow toward things this grammar can produce.
        """
        self.assertEqual(plan_paths.extract(":(glob)a.md"), ["a.md"])
        self.assertEqual(plan_paths.extract("a\nb.md"), ["b.md"])
        self.assertEqual(plan_paths.extract("a:b.md"), ["b.md"])

    def test_absolute_and_traversal_tokens_are_reachable(self):
        """These the grammar CAN produce, so they are the defensible future
        members of `malformed` (see the module docstring)."""
        got = plan_paths.extract("/etc/passwd.sh ../../up.sh ..md")
        # Codepoint order: '/' (0x2F) sorts before 'm' (0x6D), so '../../up.sh'
        # precedes '..md'.
        self.assertEqual(got, ["../../up.sh", "..md", "/etc/passwd.sh"])


class CollationTests(unittest.TestCase):
    """The canonical order is codepoint order, and it differs from the locale
    collation the replaced `sort -u` pipeline used. Asserted directly, because
    the drift check's boundary cannot see it."""

    QUARTET = "ab.md aB.md a_b.md a-b.md ./.aitask-scripts/x.sh"

    def test_output_is_codepoint_sorted(self):
        self.assertEqual(
            plan_paths.extract(self.QUARTET),
            [".aitask-scripts/x.sh", "a-b.md", "aB.md", "a_b.md", "ab.md"])

    def test_matches_lc_all_c_sort_not_ambient_sort(self):
        """Both halves matter: identical to `LC_ALL=C sort -u`, and — on a
        locale that actually collates — DIFFERENT from ambient `sort -u`. The
        second half is skipped where the two coincide (e.g. LANG=C), because
        there the assertion would be vacuously true rather than discriminating.
        """
        raw = "\n".join(["ab.md", "aB.md", "a_b.md", "a-b.md",
                         ".aitask-scripts/x.sh"]) + "\n"

        def shell_sort(env_extra):
            return subprocess.run(
                ["sort", "-u"], input=raw, capture_output=True, text=True,
                env={**os.environ, **env_extra}, check=True,
            ).stdout.split()

        c_order = shell_sort({"LC_ALL": "C"})
        self.assertEqual(plan_paths.extract(self.QUARTET), c_order)

        ambient = shell_sort({})
        if ambient == c_order:
            self.skipTest("ambient locale collates like C — not discriminating")
        self.assertNotEqual(
            plan_paths.extract(self.QUARTET), ambient,
            "extractor must NOT reproduce locale collation")


class ClassificationTests(unittest.TestCase):
    def setUp(self):
        self.tracked = {"a/b.sh", "aidocs/framework/x.md", "README.md"}
        self.dirs = set()
        for path in self.tracked:
            parts = path.split("/")
            for i in range(1, len(parts)):
                self.dirs.add("/".join(parts[:i]))

    def cls(self, token):
        return plan_paths.classify(token, self.tracked, self.dirs)

    def test_tracked(self):
        self.assertEqual(self.cls("a/b.sh"), "tracked")

    def test_planned_new_needs_a_tracked_parent_dir(self):
        self.assertEqual(self.cls("a/new.sh"), "planned_new")

    def test_phantom_when_parent_is_untracked(self):
        self.assertEqual(self.cls("aiscripts/gone.sh"), "phantom")

    def test_malformed_is_checked_first_and_beats_planned_new(self):
        """`-claude.md` has dirname '' — the repo root, trivially tracked. If
        `malformed` were not checked first, extraction garbage would land in
        the class a consumer reads as new-file-collision evidence."""
        self.assertEqual(self.cls("-claude.md"), "malformed")

    def test_root_level_untracked_file_is_phantom_not_planned_new(self):
        """The documented false negative: a GENUINE planned new top-level file
        classifies `phantom`. Pinned so the limitation is executable, not prose.
        Without the non-empty-parent rule this would be `planned_new`, and 428
        bare-filename prose mentions in the live corpus would flood the class.
        """
        self.assertEqual(self.cls("pyproject.toml"), "phantom")
        self.assertEqual(self.cls("CHANGELOG.md"), "phantom")

    def test_moved_file_classifies_planned_new_not_new_work(self):
        """The other documented limitation: `planned_new` means 'a plausibly
        createable location', never 'confirmed new work'. A file that MOVED away
        lands here too — e.g. aidocs/adding_a_new_codeagent.md, now under
        aidocs/framework/."""
        self.assertEqual(self.cls("aidocs/adding_a_new_codeagent.md"),
                         "planned_new")

    def test_classes_tuple_declares_evaluation_order(self):
        self.assertEqual(plan_paths.CLASSES[0], "malformed")


class TrackedSetsTests(unittest.TestCase):
    """`git ls-files` is asked ONCE, and a git failure is raised rather than
    returned as an empty set that would read as 'nothing is tracked'."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)
        env = {**os.environ, "GIT_CONFIG_GLOBAL": os.devnull,
               "GIT_CONFIG_SYSTEM": os.devnull}
        self.env = env
        run = lambda *a: subprocess.run(  # noqa: E731
            ["git", "-C", str(self.root), *a], check=True, env=env,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        run("init", "-q")
        run("config", "user.email", "t@e.com")
        run("config", "user.name", "T")
        (self.root / "aidocs").mkdir()
        (self.root / "aidocs" / "x.md").write_text("x\n")
        run("add", "-A")
        run("commit", "-q", "-m", "init")

    def test_returns_files_and_directory_prefixes(self):
        tracked, dirs = plan_paths.tracked_sets(self.root)
        self.assertEqual(tracked, {"aidocs/x.md"})
        self.assertEqual(dirs, {"aidocs"})

    def test_ls_files_is_bounded(self):
        """Unbounded, a wedged index.lock or a hung NFS mount blocks a caller
        that promised never to fail its own operation, and no outer budget can
        rescue a synchronous call."""
        self.assertTrue(plan_paths.LS_FILES_TIMEOUT_S > 0)
        with self.assertRaises(subprocess.TimeoutExpired):
            plan_paths.tracked_sets(self.root, timeout=0.000001)

    def test_git_failure_raises_rather_than_returning_empty(self):
        outside = Path(self._tmp.name) / "not-a-repo"
        outside.mkdir()
        with self.assertRaises((subprocess.CalledProcessError, OSError)):
            # An empty temp dir with no repo above it: git must fail, and the
            # helper must not convert that into "nothing is tracked".
            plan_paths.tracked_sets(Path(tempfile.mkdtemp()))


class ReadFailureTests(unittest.TestCase):
    def test_extract_file_propagates_io_errors(self):
        """'could not read it' must stay distinct from 'read it, found nothing'
        — the caller decides, and swallowing it here would file an I/O failure
        as a corpus fact."""
        with self.assertRaises(OSError):
            plan_paths.extract_file("/nonexistent/plan.md")


class CliTests(unittest.TestCase):
    def run_cli(self, *args):
        return subprocess.run(
            [sys.executable, str(SCRIPTS_DIR / "lib" / "plan_paths.py"), *args],
            capture_output=True, text=True)

    def test_double_dash_ends_option_parsing(self):
        with tempfile.NamedTemporaryFile("w", suffix=".md", delete=False) as fh:
            fh.write("see a/b.sh\n")
            name = fh.name
        self.addCleanup(os.unlink, name)
        got = self.run_cli("--", name)
        self.assertEqual(got.returncode, 0, got.stderr)
        self.assertEqual(got.stdout.split(), ["a/b.sh"])

    def test_unreadable_plan_exits_3_with_empty_stdout(self):
        got = self.run_cli("--", "/nonexistent/plan.md")
        self.assertEqual(got.returncode, 3)
        self.assertEqual(got.stdout, "")

    def test_usage_error_exits_2(self):
        self.assertEqual(self.run_cli().returncode, 2)


if __name__ == "__main__":
    unittest.main()
