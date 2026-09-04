"""Board task commits carry a pathspec, and stage nothing they need not (t1702).

The three board sites — `KanbanApp._do_git_commit_tasks`, `_do_delete`,
`_do_rename_task` — each ran `git commit -m <msg>` with **no pathspec** against
the shared `.aitask-data` index, so whatever a concurrent session had staged rode
along under the board's message.

MEASURED BASELINE (pre-phase mitigation `characterize_delete_commit_contents`,
run against the unmodified code before any edit, in a fixture where a child
delete also revives a folded task and a foreign session holds a staged edit):

    $ git show --name-status HEAD
    D   aiplans/p10/p10_2_beta.md
    D   aitasks/t10/t10_2_beta.md
    M   aitasks/t99_bystander.md     <-- the foreign session's staged edit
    $ git status --porcelain
     M  aitasks/t10/t10_3_gamma.md   <-- revived folded task, left DIRTY
     M  aitasks/t10_parent.md        <-- parent's children_to_implement, left DIRTY

Two facts, and the second corrected this task's plan. (1) The bystander is
swallowed — the defect. (2) The parent and revived-folded writes were **never**
in the commit: `aitask_update.sh` writes them to the worktree without staging,
and a pathspec-less `git commit` takes the *index*, so only what `git rm` had
staged plus the foreign entry landed. Widening the pathspec to include them is
therefore a fix for a pre-existing omission (those files were left ownerless,
which is what `ait sync`'s pre-sync sweep quarantines), not the avoidance of a
regression this change would otherwise introduce.

The real classes are exercised — a real `Task`, the real `KanbanApp` methods, the
workers' real bodies reached through `__wrapped__` (Textual's `@work` applies
`functools.wraps`), and a real git repository in the shared `board_fixture` tree
— so an absence here is a real absence in production code.

A FRESH tree per test, not per class: every test here commits, and a shared tree
would leave each test starting from the previous one's history — the assertions
on `HEAD` would then measure whatever ran before them.

Run: python3 tests/test_board_scoped_task_commit.py -v
  or: bash tests/run_all_python_tests.sh
"""

from __future__ import annotations

import re
import subprocess
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock

REPO_ROOT = Path(__file__).resolve().parent.parent
BOARD_PATH = REPO_ROOT / ".aitask-scripts" / "board" / "aitask_board.py"
for _p in (
    str(REPO_ROOT / "tests" / "lib"),
    str(REPO_ROOT / ".aitask-scripts"),
    str(REPO_ROOT / ".aitask-scripts" / "board"),
    str(REPO_ROOT / ".aitask-scripts" / "lib"),
):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import board_fixture as bf  # noqa: E402

#: A parent with pending children, a child that FOLDED a sibling into itself, and
#: a bystander for a concurrent session to dirty. The fold matters: deleting
#: t9000_1 revives t9000_2, which is one of the files the widened pathspec has to
#: carry.
T1702_TOPOLOGY = (
    bf.FixtureTask(task_id="9000", col="c0", idx=10, slug="parent",
                   extra={"children_to_implement": ["t9000_1"]}),
    bf.FixtureTask(task_id="9000_1", col="c0", idx=20, slug="childone",
                   extra={"folded_tasks": ["9000_2"]}),
    bf.FixtureTask(task_id="9000_2", col="c1", idx=30, slug="childtwo",
                   status="Folded", extra={"folded_into": "9000_1"}),
    bf.FixtureTask(task_id="9004", col="c4", idx=10, slug="bystander"),
)

PARENT = "aitasks/t9000_parent.md"
CHILD = "aitasks/t9000/t9000_1_childone.md"
FOLDED = "aitasks/t9000/t9000_2_childtwo.md"
CHILD_PLAN = "aiplans/p9000/p9000_1_childone.md"
BYSTANDER = "aitasks/t9004_bystander.md"


class BoardCommitTestBase(unittest.TestCase):
    """A fresh `board_fixture` tree per test, with a foreign STAGED edit in it."""

    def setUp(self):
        # enter_fixture_tree owns the chdir and its restore, which is what keeps
        # this module off the live tree (tests/test_board_fixture_harness.py).
        self.tree, self.ab = bf.enter_fixture_tree(
            self.addCleanup, tasks_spec=T1702_TOPOLOGY,
            tag=f"{type(self).__name__}_{self._testMethodName}")
        self.data = self.tree / ".aitask-data"

        # The seam shells out to ./.aitask-scripts/aitask_task_commit.sh, and the
        # delete path to ./.aitask-scripts/aitask_update.sh, both by repo-relative
        # path. Symlinked rather than copied: the scripts only ever write through
        # cwd-relative paths, so the live tree is never touched.
        (self.tree / ".aitask-scripts").symlink_to(REPO_ROOT / ".aitask-scripts")

        # The fixture tree has no aiplans layer; the delete and rename paths both
        # act on a plan file, so add one and commit it as part of the baseline.
        (self.data / "aiplans" / "p9000").mkdir(parents=True)
        (self.data / CHILD_PLAN).write_text("# plan for t9000_1\n", encoding="utf-8")
        (self.tree / "aiplans").symlink_to(Path(".aitask-data") / "aiplans")
        self._git("add", "--", CHILD_PLAN)
        self._git("commit", "-qm", "fixture plan")

        # A concurrent session's in-flight edit: committed, then modified AND
        # STAGED. This is the entry a pathspec-less commit swallows.
        p = self.data / BYSTANDER
        p.write_text(p.read_text(encoding="utf-8") + "\nMid-edit by another session.\n",
                     encoding="utf-8")
        self._git("add", "--", BYSTANDER)

    # -- git observations --------------------------------------------------

    def _git(self, *args):
        return subprocess.run(("git",) + args, cwd=self.data,
                              capture_output=True, text=True)

    def head_files(self):
        out = self._git("show", "--name-only", "--format=", "HEAD").stdout
        return [ln for ln in out.splitlines() if ln.strip()]

    def head_status(self):
        # --no-renames: git would otherwise report a rename as one `R100 old new`
        # line, which hides whether BOTH paths reached the commit. The question
        # here is pathspec coverage, so the delete/add shape is what to assert.
        out = self._git("show", "--name-status", "--no-renames", "--format=",
                        "HEAD").stdout
        return [ln for ln in out.splitlines() if ln.strip()]

    def staged(self):
        out = self._git("diff", "--cached", "--name-only").stdout
        return [ln for ln in out.splitlines() if ln.strip()]

    def commit_count(self):
        return self._git("rev-list", "--count", "HEAD").stdout.strip()

    def assert_bystander_untouched(self, where):
        self.assertNotIn(BYSTANDER, self.head_files(),
                         f"{where}: the bystander was swept into the commit")
        self.assertIn(BYSTANDER, self.staged(),
                      f"{where}: the bystander's staged entry was consumed")

    # -- worker drivers ----------------------------------------------------

    def _app(self):
        app = MagicMock()
        # Attachment decref shells out to aitask_attach.sh and is orthogonal; its
        # contract is covered by tests/test_board_decref_doomed_attachments.py.
        app._decref_doomed_attachments.return_value = (True, "")
        # The unfold is NOT stubbed: it is what writes the revived folded task.
        app._unfold_deleted_primary_children = (
            lambda ids: self.ab.KanbanApp._unfold_deleted_primary_children(app, ids))
        return app

    def notifications(self, app):
        # The workers dispatch through `self.app.call_from_thread`, so with a
        # MagicMock `self` the recorder is the CHILD mock `app.app`, not `app`.
        out = []
        for c in app.app.call_from_thread.call_args_list:
            if len(c.args) > 1 and isinstance(c.args[1], str):
                out.append((c.args[1], c.kwargs.get("severity")))
        return out


class CommitDialogTests(BoardCommitTestBase):
    """_do_git_commit_tasks commits the dialog's task files and nothing else."""

    def test_commits_only_its_own_paths(self):
        p = self.data / PARENT
        p.write_text(p.read_text(encoding="utf-8") + "\nEdited via the board.\n",
                     encoding="utf-8")
        app = self._app()

        self.ab.KanbanApp._do_git_commit_tasks.__wrapped__(
            app, [PARENT], 1, "ait: Update t9000", "")

        self.assertEqual([PARENT], self.head_files())
        self.assert_bystander_untouched("commit dialog")
        self.assertEqual([("Committed 1 file(s)", "information")],
                         self.notifications(app))

    def test_a_new_untracked_task_file_still_commits(self):
        (self.data / "aitasks" / "t9007_new.md").write_text(
            "---\nstatus: Ready\n---\n\nNew.\n", encoding="utf-8")
        app = self._app()

        self.ab.KanbanApp._do_git_commit_tasks.__wrapped__(
            app, ["aitasks/t9007_new.md"], 1, "ait: Add t9007", "")

        self.assertEqual(["aitasks/t9007_new.md"], self.head_files())
        self.assert_bystander_untouched("commit dialog / new file")

    def test_nothing_to_commit_is_a_warning_not_a_failure(self):
        app = self._app()
        before = self.commit_count()

        self.ab.KanbanApp._do_git_commit_tasks.__wrapped__(
            app, [PARENT], 1, "ait: no-op", "")

        self.assertEqual(before, self.commit_count())
        self.assertEqual([("Nothing to commit", "warning")],
                         self.notifications(app))


class DeleteTests(BoardCommitTestBase):
    """_do_delete: scoped pathspec, widened to what it wrote, staging nothing."""

    DOOMED = [CHILD, CHILD_PLAN]
    CO_WRITTEN = [PARENT, FOLDED]

    def _run_delete(self, app, extra_paths):
        self.ab.KanbanApp._do_delete.__wrapped__(
            app, "t9000_1", list(self.DOOMED), ["9000_2"], "t9000", extra_paths)

    def test_execute_delete_resolves_the_co_written_paths(self):
        """The resolver half: _execute_delete must hand the worker the parent and
        the revived folded task, not only the doomed files."""
        app = self._app()
        task = self.ab.Task(Path(CHILD))

        self.ab.KanbanApp._execute_delete(app, "t9000_1", [task.filepath], task)

        extra_paths = app._do_delete.call_args.args[4]
        self.assertIn(PARENT, extra_paths,
                      "the parent's children_to_implement edit is not committed")
        self.assertIn(FOLDED, extra_paths,
                      "the revived folded task is not committed")

    def test_commit_carries_the_doomed_and_the_co_written_paths(self):
        app = self._app()
        self._run_delete(app, self.CO_WRITTEN)

        status = self.head_status()
        self.assertIn(f"D\t{CHILD}", status)
        self.assertIn(f"D\t{CHILD_PLAN}", status)
        self.assertIn(f"M\t{PARENT}", status)
        self.assertIn(f"M\t{FOLDED}", status)
        self.assert_bystander_untouched("delete")

    def test_nothing_the_delete_wrote_is_left_dirty(self):
        app = self._app()
        self._run_delete(app, self.CO_WRITTEN)

        dirty = self._git("status", "--porcelain", "--",
                          "aitasks/", "aiplans/").stdout
        self.assertNotIn("t9000_parent", dirty)
        self.assertNotIn("t9000_2_childtwo", dirty)

    def test_the_delete_stages_nothing_of_its_own(self):
        """`git rm` would park staged deletions in the SHARED index for the whole
        window before this operation's own commit, where anyone's index-wide
        commit collects them. The spy reads the index at the moment the seam is
        entered — the widest that window ever gets."""
        seen = {}
        real = self.ab.commit_task_paths

        def spy(message, paths, **kw):
            seen["staged"] = self.staged()
            return real(message, paths, **kw)

        self.ab.commit_task_paths = spy
        try:
            self._run_delete(self._app(), self.CO_WRITTEN)
        finally:
            self.ab.commit_task_paths = real

        self.assertEqual(
            [BYSTANDER], seen["staged"],
            "the delete staged something of its own before its scoped commit")


class RenameTests(BoardCommitTestBase):
    """_do_rename_task commits both halves without touching the shared index."""

    def test_commits_both_halves_only(self):
        app = self._app()
        new_task = "aitasks/t9000/t9000_1_renamed.md"
        new_plan = "aiplans/p9000/p9000_1_renamed.md"

        self.ab.KanbanApp._do_rename_task.__wrapped__(
            app, Path(CHILD), Path(new_task),
            Path(CHILD_PLAN), Path(new_plan),
            "t9000_1", "renamed", "t9000_1_renamed.md",
        )

        status = self.head_status()
        self.assertIn(f"D\t{CHILD}", status)
        self.assertIn(f"A\t{new_task}", status)
        self.assertIn(f"D\t{CHILD_PLAN}", status)
        self.assertIn(f"A\t{new_plan}", status)
        self.assert_bystander_untouched("rename")


class NegativeControlTests(BoardCommitTestBase):
    """Route the same worker bodies to the PRE-FIX seam; every guarantee flips.

    The bodies are untouched — only `commit_task_paths` is swapped for what the
    three sites did before t1702 (stage our paths, then commit with no pathspec).
    A control whose injection silently failed cannot pass: each assertion below
    asserts the defect POSITIVELY.
    """

    def _install_prefix_seam(self):
        real = self.ab.commit_task_paths
        Result = real.__globals__["CommitResult"]

        def legacy(message, paths, **kw):
            for p in paths:
                self._git("add", "--", str(p))
            r = self._git("commit", "-m", str(message), "--quiet")
            if r.returncode == 0:
                return Result("committed", str(message), None)
            return Result("failed", None, (r.stderr or r.stdout).strip())

        self.ab.commit_task_paths = legacy
        self.addCleanup(setattr, self.ab, "commit_task_paths", real)

    def test_prefix_seam_sweeps_the_bystander_on_a_commit(self):
        self._install_prefix_seam()
        p = self.data / PARENT
        p.write_text(p.read_text(encoding="utf-8") + "\nEdited via the board.\n",
                     encoding="utf-8")

        self.ab.KanbanApp._do_git_commit_tasks.__wrapped__(
            self._app(), [PARENT], 1, "ait: Update t9000", "")

        self.assertIn(BYSTANDER, self.head_files(),
                      "control did not reproduce the defect — it proves nothing")
        self.assertEqual([], self.staged(),
                         "control did not consume the foreign staged entry")

    def test_prefix_seam_sweeps_the_bystander_on_a_delete(self):
        self._install_prefix_seam()

        self.ab.KanbanApp._do_delete.__wrapped__(
            self._app(), "t9000_1", [CHILD, CHILD_PLAN], ["9000_2"], "t9000",
            [PARENT, FOLDED])

        self.assertIn(BYSTANDER, self.head_files(),
                      "control did not reproduce the defect — it proves nothing")


class SourceGuardTests(unittest.TestCase):
    """No board site may go back to a pathspec-less commit.

    A literal-construct scan, not a semantic parse: it matches the exact argv
    shape the three sites used, which is precise enough to have no false
    positives and specific enough that reintroducing one is caught.
    """

    PATTERN = r'\[\*_task_git_cmd\(\),\s*"commit".*'

    def test_no_pathspec_less_task_git_commit_in_the_board(self):
        offenders = [m.group(0) for m in
                     re.finditer(self.PATTERN, BOARD_PATH.read_text())]
        self.assertEqual(
            [], offenders,
            "a board git-commit site bypasses lib/task_commit.commit_task_paths; "
            "a bare commit takes the whole shared .aitask-data index (t1702)")

    def test_the_guard_would_catch_the_pre_fix_line(self):
        """The guard's own negative control: without it, the scan above could
        pass by matching nothing at all."""
        pre_fix = '                [*_task_git_cmd(), "commit", "-m", message],'
        self.assertRegex(pre_fix, self.PATTERN)


if __name__ == "__main__":
    unittest.main(verbosity=2)
