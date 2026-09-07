"""The cross-repo config push owns its commit in the destination (t1704).

Why this file exists
--------------------
t1677 gave every tracked ``aitasks/metadata/*`` write in THIS repo an owner that
commits it. One writer was deliberately left out and sat in the inventory
guard's ``KNOWN_UNCOMMITTED`` allowlist: ``cross_repo_settings.apply_push``,
which writes **another** repo's tracked ``codeagent_config.json`` and returned
None, leaving the file dirty in a repo the pushing session does not own. `ait
sync` there then refuses to attribute it to any task (t1599_3), so it becomes a
permanent rebase deferral in someone else's checkout.

The commit is the easy half. The hard half — and the substance of these tests —
is deciding what is safe when the target repo is mid-work, and **reporting**
whatever is decided. A silent dirty file in someone else's repo is the defect;
a refusal the user can see is not.

Every case below is written to fail against the old write-without-commit
behaviour, and the concurrency cases carry explicit negative controls that
reproduce the exact misattribution the guards prevent.

Fixtures are real git repos in the production branch-mode topology, built by
``tests/lib/branch_mode_repo.py``. **cwd stays elsewhere throughout** — the whole
point of the seam is that it targets a foreign root by path, and a fixture that
chdir'd into the repo under test could not show that.

Run: bash tests/run_all_python_tests.sh
  or: python3 tests/test_cross_repo_push_commit.py
"""
from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / ".aitask-scripts" / "lib"))
sys.path.insert(0, str(REPO_ROOT / "tests" / "lib"))

import branch_mode_repo as bmr  # noqa: E402
import cross_repo_settings as crs  # noqa: E402
import metadata_commit  # noqa: E402

PROJECT_REL = "aitasks/metadata/codeagent_config.json"
LOCAL_REL = "aitasks/metadata/codeagent_config.local.json"


class PushCommitCase(unittest.TestCase):
    """Base: a temp dir, and a cwd assertion that keeps the fixtures honest."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="t1704-"))
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self._cwd_at_entry = os.getcwd()

    def tearDown(self):
        # A regression here would mean the seam (or a fixture) moved the
        # process, which is exactly the property that makes "targets a foreign
        # root" meaningful.
        self.assertEqual(
            os.getcwd(), self._cwd_at_entry,
            "the push must never chdir the calling process",
        )

    def project_config(self, root) -> dict:
        return json.loads((Path(root) / PROJECT_REL).read_text(encoding="utf-8"))

    def project_bytes(self, root) -> bytes:
        return (Path(root) / PROJECT_REL).read_bytes()


# ---------------------------------------------------------------------------
# The happy path and the ownership it establishes
# ---------------------------------------------------------------------------


class CommitsInDestinationTests(PushCommitCase):

    def test_clean_target_is_written_and_committed_path_scoped(self):
        """Case 1 — the whole point of the task.

        Negative control: the old code returned None and left the file dirty,
        so both the outcome assertion and the worktree-clean assertion fail
        against it.
        """
        root = bmr.make_branch_mode_repo(
            self.tmp / "clean", project={"pick": "claudecode/opus5"}
        )
        before_head = bmr.data_head(root)

        out = crs.apply_push("claudecode/sonnet5", root, "pick", "project")

        self.assertEqual(out.kind, "committed")
        self.assertTrue(out.wrote)
        self.assertIsNone(out.reason)
        # The write landed.
        self.assertEqual(
            self.project_config(root)["defaults"]["pick"], "claudecode/sonnet5"
        )
        # It was committed, in THAT repo, scoped to exactly the one path.
        self.assertNotEqual(bmr.data_head(root), before_head)
        self.assertEqual(bmr.head_files(root), [PROJECT_REL])
        self.assertEqual(
            bmr.head_subject(root), "ait: Update codeagent_config.json"
        )
        # And the destination is left clean — no ownerless dirty file.
        self.assertTrue(
            bmr.worktree_clean(root),
            "the destination's data worktree must be clean afterwards",
        )

    def test_foreign_staged_content_is_not_swept_into_the_commit(self):
        """Case 2 — a scoped commit is mandatory, never a bare `git commit`.

        Same defect class as t1702. `commit -o -- <path>` takes that path's
        worktree content and ignores the index, so a foreign staged entry
        survives untouched.
        """
        root = bmr.make_branch_mode_repo(
            self.tmp / "staged", project={"pick": "claudecode/opus5"}
        )
        foreign = Path(root) / ".aitask-data" / "aitasks" / "t99_foreign.md"
        foreign.write_text("---\nstatus: Ready\n---\nforeign\n", encoding="utf-8")
        bmr.data_git(root, "add", "--", "aitasks/t99_foreign.md")
        self.assertIn("aitasks/t99_foreign.md", bmr.staged_paths(root))

        out = crs.apply_push("claudecode/sonnet5", root, "pick", "project")

        self.assertEqual(out.kind, "committed")
        self.assertNotIn("aitasks/t99_foreign.md", bmr.head_files(root))
        self.assertIn(
            "aitasks/t99_foreign.md", bmr.staged_paths(root),
            "the foreign entry must still be staged and uncommitted",
        )

    def test_absent_project_config_is_created_and_committed(self):
        """Case 9 — the --allow-new path, derived from a pre-write existence
        check rather than hard-coded."""
        root = bmr.make_branch_mode_repo(self.tmp / "absent", project=None)
        self.assertFalse((Path(root) / PROJECT_REL).exists())

        out = crs.apply_push("claudecode/sonnet5", root, "pick", "project")

        self.assertEqual(out.kind, "committed")
        self.assertEqual(bmr.head_files(root), [PROJECT_REL])
        self.assertTrue(bmr.worktree_clean(root))

    def test_local_layer_is_written_but_never_committed(self):
        """Case 8 — the user layer is gitignored there; nothing to commit, and
        that is reported rather than looking like a failure."""
        root = bmr.make_branch_mode_repo(
            self.tmp / "userlayer", project={"pick": "claudecode/opus5"}
        )
        before_head = bmr.data_head(root)

        out = crs.apply_push("claudecode/sonnet5", root, "pick", "local")

        self.assertEqual(out.kind, "user_layer_only")
        self.assertTrue(out.wrote)
        self.assertEqual(
            json.loads((Path(root) / LOCAL_REL).read_text())["defaults"]["pick"],
            "claudecode/sonnet5",
        )
        self.assertEqual(
            bmr.data_head(root), before_head,
            "the gitignored user layer must not produce a commit",
        )


# ---------------------------------------------------------------------------
# The refusals — every one of these writes NOTHING
# ---------------------------------------------------------------------------


class RefusesMidWorkDestinationTests(PushCommitCase):

    def assert_wrote_nothing(self, root, out, reason, before_bytes, before_head):
        self.assertEqual(out.kind, "refused")
        self.assertEqual(out.reason, reason)
        self.assertFalse(out.wrote, "a refusal must not have written anything")
        self.assertIsNotNone(out.detail, "a refusal must say what it saw")
        if before_bytes is not None:
            self.assertEqual(
                self.project_bytes(root), before_bytes,
                "their bytes must survive byte-for-byte",
            )
        self.assertEqual(bmr.data_head(root), before_head)

    def test_dirty_target_config_is_refused_before_writing(self):
        """Case 3 — their session is mid-edit.

        Negative control: the old code overwrote those bytes unconditionally,
        so the byte-preservation assertion fails against it.
        """
        root = bmr.make_branch_mode_repo(
            self.tmp / "dirty", project={"pick": "claudecode/opus5"}
        )
        (Path(root) / PROJECT_REL).write_text(
            json.dumps({"defaults": {"pick": "claudecode/haiku4_5"}}) + "\n",
            encoding="utf-8",
        )
        before_bytes = self.project_bytes(root)
        before_head = bmr.data_head(root)

        out = crs.apply_push("claudecode/sonnet5", root, "pick", "project")

        self.assert_wrote_nothing(
            root, out, crs.REASON_DEST_MID_WORK, before_bytes, before_head
        )

    def test_untracked_target_config_is_refused(self):
        """Case 10 — present but untracked is unclassified foreign content."""
        root = bmr.make_branch_mode_repo(
            self.tmp / "untracked", project={"pick": "claudecode/opus5"},
            commit_config=False,
        )
        before_bytes = self.project_bytes(root)
        before_head = bmr.data_head(root)

        out = crs.apply_push("claudecode/sonnet5", root, "pick", "project")

        self.assert_wrote_nothing(
            root, out, crs.REASON_DEST_UNTRACKED_CONFIG, before_bytes, before_head
        )

    def test_mid_operation_worktree_is_refused(self):
        """Case 4 — planted in the data worktree's REAL gitdir, as git would."""
        root = bmr.make_branch_mode_repo(
            self.tmp / "midop", project={"pick": "claudecode/opus5"}
        )
        before_bytes = self.project_bytes(root)
        before_head = bmr.data_head(root)
        bmr.plant_inprogress_state(root, "MERGE_HEAD")

        out = crs.apply_push("claudecode/sonnet5", root, "pick", "project")

        self.assert_wrote_nothing(
            root, out, crs.REASON_DEST_MID_OPERATION, before_bytes, before_head
        )
        self.assertIn("MERGE_HEAD", out.detail)

    def test_every_inprogress_state_is_refused(self):
        """The refusal is not special-cased to merge.

        Walks the SAME constant the production guard reads, so a state added
        there is covered here without editing this test — and a state dropped
        from it fails `tests/test_task_git.sh` Test 16 rather than passing
        silently.
        """
        states = _inprogress_states_from_shell()
        self.assertEqual(len(states), 6, f"unexpected state set: {states}")
        for state in states:
            with self.subTest(state=state):
                root = bmr.make_branch_mode_repo(
                    self.tmp / f"midop_{state}",
                    project={"pick": "claudecode/opus5"},
                )
                before_bytes = self.project_bytes(root)
                bmr.plant_inprogress_state(root, state)
                out = crs.apply_push(
                    "claudecode/sonnet5", root, "pick", "project"
                )
                self.assertEqual(out.reason, crs.REASON_DEST_MID_OPERATION)
                self.assertFalse(out.wrote)
                self.assertEqual(self.project_bytes(root), before_bytes)

    def test_detached_data_head_is_refused(self):
        """Case 5 — a commit on a detached HEAD would be unreachable."""
        root = bmr.make_branch_mode_repo(
            self.tmp / "detached", project={"pick": "claudecode/opus5"}
        )
        before_bytes = self.project_bytes(root)
        before_head = bmr.data_head(root)
        bmr.detach_data_head(root)

        out = crs.apply_push("claudecode/sonnet5", root, "pick", "project")

        self.assert_wrote_nothing(
            root, out, crs.REASON_DEST_DETACHED_HEAD, before_bytes, before_head
        )

    def test_legacy_layout_target_is_refused(self):
        """Case 6 — committing there lands on whatever code branch is checked
        out, which is why legacy is the only branch-sensitive case."""
        root = bmr.make_legacy_repo(
            self.tmp / "legacy", project={"pick": "claudecode/opus5"}
        )
        before_bytes = self.project_bytes(root)

        out = crs.apply_push("claudecode/sonnet5", root, "pick", "project")

        self.assertEqual(out.kind, "refused")
        self.assertEqual(out.reason, crs.REASON_DEST_LEGACY_LAYOUT)
        self.assertFalse(out.wrote)
        self.assertEqual(self.project_bytes(root), before_bytes)

    def test_target_without_the_commit_helper_is_refused(self):
        """Case 7 — fail-closed against version skew.

        A destination not yet upgraded past t1677 has no
        aitask_metadata_commit.sh at all. Refusing is correct; writing on the
        assumption it would work is what would leave the ownerless file.
        """
        root = bmr.make_branch_mode_repo(
            self.tmp / "skew", project={"pick": "claudecode/opus5"},
            install_helper=False,
        )
        before_bytes = self.project_bytes(root)
        before_head = bmr.data_head(root)

        out = crs.apply_push("claudecode/sonnet5", root, "pick", "project")

        self.assert_wrote_nothing(
            root, out, crs.REASON_DEST_COMMIT_UNAVAILABLE,
            before_bytes, before_head,
        )

    def test_helper_too_old_to_know_preflight_is_refused(self):
        """Version skew's realistic shape: the helper EXISTS but predates
        --preflight.

        The discriminating case for requiring the protocol's own MODE: line
        rather than trusting exit 0: an older helper answers an unknown flag
        with its usage text and exit 0, which a laxer parse would read as a
        successful inspection of a clean destination.
        """
        root = bmr.make_branch_mode_repo(
            self.tmp / "oldhelper", project={"pick": "claudecode/opus5"}
        )
        helper = Path(root) / ".aitask-scripts" / "aitask_metadata_commit.sh"
        helper.write_text(
            "#!/usr/bin/env bash\n"
            "# An older copy: it does not know --preflight and prints usage.\n"
            "echo 'Usage: aitask_metadata_commit.sh [--allow-new] <path>...'\n"
            "exit 0\n",
            encoding="utf-8",
        )
        helper.chmod(0o755)
        before_bytes = self.project_bytes(root)

        out = crs.apply_push("claudecode/sonnet5", root, "pick", "project")

        self.assertEqual(out.reason, crs.REASON_DEST_COMMIT_UNAVAILABLE)
        self.assertFalse(out.wrote)
        self.assertEqual(self.project_bytes(root), before_bytes)


# ---------------------------------------------------------------------------
# Commit failure and the remedy it must advertise
# ---------------------------------------------------------------------------


class CommitFailureTests(PushCommitCase):

    def test_commit_failure_keeps_the_write_and_names_a_runnable_remedy(self):
        """Case 12 — the write survives on disk (losing the user's edit to a
        commit error would be worse than a dirty file), and the detail carries
        a command they can actually run."""
        root = bmr.make_branch_mode_repo(
            self.tmp / "hookfail", project={"pick": "claudecode/opus5"}
        )
        bmr.install_failing_pre_commit(root)
        before_head = bmr.data_head(root)

        out = crs.apply_push("claudecode/sonnet5", root, "pick", "project")

        self.assertEqual(out.kind, "commit_failed")
        self.assertTrue(out.wrote)
        self.assertEqual(
            self.project_config(root)["defaults"]["pick"], "claudecode/sonnet5",
            "the write must survive a commit failure",
        )
        self.assertEqual(bmr.data_head(root), before_head)
        self.assertIsNotNone(out.detail)
        self.assertIn(f"cd {root}", out.detail)
        self.assertIn("aitask_metadata_commit.sh", out.detail)
        self.assertIn(PROJECT_REL, out.detail)

    def test_remedy_for_a_created_file_carries_allow_new(self):
        """A file this run CREATED is left untracked by the failure path, so a
        remedy without --allow-new would answer REFUSED:untracked and clear
        nothing — worse than no advice, because the user concludes it is
        unfixable."""
        root = bmr.make_branch_mode_repo(self.tmp / "hookfail_new", project=None)
        bmr.install_failing_pre_commit(root)

        out = crs.apply_push("claudecode/sonnet5", root, "pick", "project")

        self.assertEqual(out.kind, "commit_failed")
        self.assertIn("--allow-new", out.detail)


# ---------------------------------------------------------------------------
# clear_mask ordering — the durability gate
# ---------------------------------------------------------------------------


class ClearMaskOrderingTests(PushCommitCase):

    def test_clear_after_a_successful_commit_pins_step_7_ordering(self):
        """Case 11 — the clear fails AFTER a successful commit.

        Pins that the project write is already ON THE DATA BRANCH by the time
        the clear runs, not merely on disk.
        """
        root = bmr.make_branch_mode_repo(
            self.tmp / "cm_order",
            project={"pick": "claudecode/opus5"},
            local={"pick": "claudecode/sonnet5", "explore": "claudecode/opus5"},
        )
        observed = {}

        def fail_clear(path, data):
            observed["committed_at_clear_time"] = bmr.data_git(
                root, "show", f"HEAD:{PROJECT_REL}"
            )
            raise OSError("disk full")

        with mock.patch.object(crs, "save_local_config", side_effect=fail_clear):
            with self.assertRaises(crs.PushPartialError) as ctx:
                crs.apply_push("claudecode/haiku4_5", root, "pick", "project",
                               clear_mask=True)

        self.assertEqual(ctx.exception.commit_kind, "committed")
        self.assertIn(
            "claudecode/haiku4_5", observed["committed_at_clear_time"],
            "the project write must be COMMITTED before the mask is cleared",
        )

    def test_a_failed_commit_keeps_the_mask(self):
        """Case 15 (commit_failed half) — clearing the mask while the project
        file sits uncommitted would leave the repo using a value that exists
        only as a dirty file.

        Negative control: with the step-7 durability gate removed, the override
        is gone while the project file is dirty — asserted directly below.
        """
        root = bmr.make_branch_mode_repo(
            self.tmp / "cm_failed",
            project={"pick": "claudecode/opus5"},
            local={"pick": "claudecode/sonnet5", "explore": "claudecode/opus5"},
        )
        bmr.install_failing_pre_commit(root)
        before_effective = crs.read_operation_defaults(root)["pick"].effective

        out = crs.apply_push("claudecode/haiku4_5", root, "pick", "project",
                             clear_mask=True)

        self.assertEqual(out.kind, "commit_failed")
        self.assertTrue(out.mask_kept, "the mask must be KEPT on a failed commit")
        local = json.loads((Path(root) / LOCAL_REL).read_text())
        self.assertEqual(
            local["defaults"]["pick"], "claudecode/sonnet5",
            "the local override must still be there",
        )
        self.assertEqual(
            crs.read_operation_defaults(root)["pick"].effective,
            before_effective,
            "the destination's effective value must be exactly as it was",
        )


# ---------------------------------------------------------------------------
# Concurrency — faults injected through documented seams, no sleeps or threads
# ---------------------------------------------------------------------------


class ConcurrencyGuardTests(PushCommitCase):
    """The two windows, and what each guard does and does not buy.

    This is detect-and-refuse, not mutual exclusion. The guarantee under test is
    narrow and exact: the framework never PUBLISHES bytes it did not write, and
    never silently DISCARDS an edit it found.
    """

    RACER = json.dumps({"defaults": {"pick": "claudecode/RACER"}}) + "\n"

    def test_write_side_race_inside_the_preflight_window_is_refused(self):
        """Case 13 — a racer lands inside the preflight subprocess's window.

        Injected through the documented seam: the wrapper returns the real
        clean verdict AND rewrites the file as a side effect, which is exactly
        what a concurrent writer does in those tens of milliseconds.
        """
        root = bmr.make_branch_mode_repo(
            self.tmp / "race_write", project={"pick": "claudecode/opus5"}
        )
        real = crs.preflight_metadata

        def racing_preflight(paths, **kwargs):
            result = real(paths, **kwargs)
            (Path(root) / PROJECT_REL).write_text(self.RACER, encoding="utf-8")
            return result

        with mock.patch.object(crs, "preflight_metadata", racing_preflight):
            out = crs.apply_push("claudecode/sonnet5", root, "pick", "project")

        self.assertEqual(out.kind, "refused")
        self.assertEqual(out.reason, crs.REASON_DEST_MID_WORK)
        self.assertFalse(out.wrote)
        self.assertEqual(
            (Path(root) / PROJECT_REL).read_text(encoding="utf-8"), self.RACER,
            "the racer's bytes must survive byte-for-byte",
        )

    def test_write_side_control_without_the_reread_clobbers_the_racer(self):
        """The negative control for the case above.

        Without the step-4 re-read, the same injection destroys the racer's
        edit. Simulated by driving the sequence the un-guarded code would run —
        preflight, then write — so the assertion above can actually fail.
        """
        root = bmr.make_branch_mode_repo(
            self.tmp / "race_write_ctl", project={"pick": "claudecode/opus5"}
        )
        crs.preflight_metadata([PROJECT_REL], root=root, env=crs.resolver_env())
        (Path(root) / PROJECT_REL).write_text(self.RACER, encoding="utf-8")
        # The un-guarded write: exactly what apply_push did before this task.
        from config_utils import import_all_configs
        import_all_configs(
            bundle={"files": {"codeagent_config.json":
                              {"defaults": {"pick": "claudecode/sonnet5"}}}},
            metadata_dir=crs.dest_metadata_dir(root),
            overwrite=True, merge=True,
        )
        self.assertNotEqual(
            (Path(root) / PROJECT_REL).read_text(encoding="utf-8"), self.RACER,
            "control: without the re-read the racer's edit IS clobbered",
        )

    def test_commit_side_race_publishes_nothing(self):
        """Case 14 — the damaging one.

        The wrapper mutates the file and then CALLS THROUGH to the real
        function, so the real helper runs with the real --expect value. Nothing
        is stubbed at the point the guard actually fires.
        """
        root = bmr.make_branch_mode_repo(
            self.tmp / "race_commit", project={"pick": "claudecode/opus5"}
        )
        before_head = bmr.data_head(root)
        real = crs.commit_metadata

        def racing_commit(paths, **kwargs):
            (Path(root) / PROJECT_REL).write_text(self.RACER, encoding="utf-8")
            return real(paths, **kwargs)

        with mock.patch.object(crs, "commit_metadata", racing_commit):
            out = crs.apply_push("claudecode/sonnet5", root, "pick", "project")

        self.assertEqual(out.kind, "commit_raced")
        self.assertEqual(
            bmr.data_head(root), before_head,
            "no commit may be made on the destination's data branch",
        )
        self.assertEqual(
            (Path(root) / PROJECT_REL).read_text(encoding="utf-8"), self.RACER,
            "the racer's bytes are still on disk",
        )

    def test_commit_side_control_without_expect_publishes_the_racers_bytes(self):
        """The negative control for the case above — and the reason the guard
        exists at all.

        With expect=None the same injection COMMITS, and
        `git show HEAD:<path>` returns the racer's bytes under the framework's
        own "ait: Update codeagent_config.json" message. That is the framework
        attributing content it never wrote — precisely what t1599_3's
        quarantine was built to stop.
        """
        root = bmr.make_branch_mode_repo(
            self.tmp / "race_commit_ctl", project={"pick": "claudecode/opus5"}
        )
        real = crs.commit_metadata

        def racing_commit_unguarded(paths, **kwargs):
            (Path(root) / PROJECT_REL).write_text(self.RACER, encoding="utf-8")
            kwargs["expect"] = None
            return real(paths, **kwargs)

        with mock.patch.object(crs, "commit_metadata", racing_commit_unguarded):
            out = crs.apply_push("claudecode/sonnet5", root, "pick", "project")

        self.assertEqual(out.kind, "committed")
        self.assertEqual(
            bmr.head_subject(root), "ait: Update codeagent_config.json"
        )
        self.assertIn(
            "claudecode/RACER", bmr.data_git(root, "show", f"HEAD:{PROJECT_REL}"),
            "control: unguarded, the racer's bytes ARE published under our message",
        )

    def test_a_raced_commit_keeps_the_mask(self):
        """Case 15 (commit_raced half) — the mask must survive a race too.

        Clearing it here would be worse than after a plain failure: the project
        file holds someone ELSE's bytes.
        """
        root = bmr.make_branch_mode_repo(
            self.tmp / "race_mask",
            project={"pick": "claudecode/opus5"},
            local={"pick": "claudecode/sonnet5", "explore": "claudecode/opus5"},
        )
        before_effective = crs.read_operation_defaults(root)["pick"].effective
        real = crs.commit_metadata

        def racing_commit(paths, **kwargs):
            (Path(root) / PROJECT_REL).write_text(self.RACER, encoding="utf-8")
            return real(paths, **kwargs)

        with mock.patch.object(crs, "commit_metadata", racing_commit):
            out = crs.apply_push("claudecode/haiku4_5", root, "pick", "project",
                                 clear_mask=True)

        self.assertEqual(out.kind, "commit_raced")
        self.assertTrue(out.mask_kept)
        local = json.loads((Path(root) / LOCAL_REL).read_text())
        self.assertEqual(local["defaults"]["pick"], "claudecode/sonnet5")
        self.assertEqual(
            crs.read_operation_defaults(root)["pick"].effective, before_effective,
            "the destination's effective value must be unchanged",
        )


# ---------------------------------------------------------------------------
# Environment isolation — the hazard resolver_env() already exists to close
# ---------------------------------------------------------------------------


class EnvironmentScrubTests(PushCommitCase):

    def test_a_leaked_task_dir_does_not_aim_the_commit_at_the_wrong_tree(self):
        """The helper's METADATA_PREFIX reads ${TASK_DIR:-aitasks}, so a
        TASK_DIR leaking from the pushing session would make the destination's
        own helper resolve a different tree — and refuse our in-scope path as
        out_of_scope."""
        root = bmr.make_branch_mode_repo(
            self.tmp / "envleak", project={"pick": "claudecode/opus5"}
        )
        with mock.patch.dict(os.environ, {"TASK_DIR": "somewhere_else"}):
            out = crs.apply_push("claudecode/sonnet5", root, "pick", "project")

        self.assertEqual(
            out.kind, "committed",
            "the scrubbed env must keep the destination resolving its own tree",
        )
        self.assertEqual(bmr.head_files(root), [PROJECT_REL])


# ---------------------------------------------------------------------------
# The constants that must agree with each other
# ---------------------------------------------------------------------------


class PathConstantAgreementTests(PushCommitCase):

    def test_repo_relative_path_agrees_with_dest_metadata_dir(self):
        """The commit is aimed by a repo-relative string while the write is
        aimed by dest_metadata_dir(). A drift between them would commit a path
        the write never touched — and the commit would silently do nothing."""
        root = self.tmp / "agree"
        (root / "aitasks" / "metadata").mkdir(parents=True)
        for name in (crs.PROJECT_CONFIG_NAME, crs.LOCAL_CONFIG_NAME):
            derived = crs.dest_metadata_dir(root) / name
            rel = crs._repo_relative_config(name)
            self.assertEqual(
                derived, root / rel,
                f"{rel} must name the same file dest_metadata_dir() writes",
            )


# ---------------------------------------------------------------------------
# What the user actually sees — the syncer's per-destination result lines
# ---------------------------------------------------------------------------


class ResultLineRenderingTests(PushCommitCase):
    """Every outcome must be REPORTED. Capturing a diagnostic is not surfacing
    it, so these drive real outcomes from real fixtures through the real
    renderer rather than asserting on the dataclass alone.
    """

    @classmethod
    def setUpClass(cls):
        sys.path.insert(0, str(REPO_ROOT / ".aitask-scripts" / "syncer"))
        import syncer_app
        cls.render = staticmethod(syncer_app._render_apply_outcome)

    def line_for(self, out, layer="project"):
        return type(self).render(out, layer)

    def test_a_successful_push_says_it_committed_and_did_not_push(self):
        root = bmr.make_branch_mode_repo(
            self.tmp / "r_ok", project={"pick": "claudecode/opus5"}
        )
        line = self.line_for(crs.apply_push("claudecode/sonnet5", root, "pick",
                                            "project"))
        self.assertIn("committed there", line)
        self.assertIn("not pushed", line,
                      "a user who assumes it pushed will not go and push it")

    def test_every_refusal_reason_renders_a_distinct_user_facing_line(self):
        """No refusal may fall through to a bare reason token, and no two may
        render identically — a user has to be able to tell a mid-edit from a
        repo that needs upgrading."""
        seen = {}
        for reason in (
            crs.REASON_DEST_MID_WORK,
            crs.REASON_DEST_UNTRACKED_CONFIG,
            crs.REASON_DEST_MID_OPERATION,
            crs.REASON_DEST_DETACHED_HEAD,
            crs.REASON_DEST_LEGACY_LAYOUT,
            crs.REASON_DEST_COMMIT_UNAVAILABLE,
        ):
            out = crs.ApplyOutcome(kind="refused", reason=reason, detail=None)
            line = self.line_for(out)
            self.assertNotIn(reason, line,
                             f"{reason} leaked its raw token into the UI")
            self.assertTrue(line.startswith("not applied:"))
            self.assertNotIn(line, seen,
                             f"{reason} renders the same as {seen.get(line)}")
            seen[line] = reason

    def test_a_mid_operation_refusal_names_the_state(self):
        """The only refusal whose detail is user-meaningful: it tells them which
        `--abort` to run over there."""
        root = bmr.make_branch_mode_repo(
            self.tmp / "r_midop", project={"pick": "claudecode/opus5"}
        )
        bmr.plant_inprogress_state(root, "CHERRY_PICK_HEAD")
        line = self.line_for(crs.apply_push("claudecode/sonnet5", root, "pick",
                                            "project"))
        self.assertIn("CHERRY_PICK_HEAD", line)

    def test_a_version_skew_refusal_does_not_leak_a_raw_exception(self):
        """dest_commit_unavailable's detail is a Python error string. Shown
        verbatim it reads as a crash rather than as "that repo needs
        upgrading", so the renderer must not surface it."""
        root = bmr.make_branch_mode_repo(
            self.tmp / "r_skew", project={"pick": "claudecode/opus5"},
            install_helper=False,
        )
        out = crs.apply_push("claudecode/sonnet5", root, "pick", "project")
        line = self.line_for(out)

        self.assertIsNotNone(out.detail, "the diagnostic is still captured")
        self.assertIn("Errno", out.detail)
        self.assertNotIn("Errno", line, "but it must not reach the user")
        self.assertIn("Versions tab", line, "the line must say what to DO")

    def test_a_failed_commit_line_carries_the_runnable_remedy(self):
        root = bmr.make_branch_mode_repo(
            self.tmp / "r_fail", project={"pick": "claudecode/opus5"}
        )
        bmr.install_failing_pre_commit(root)
        line = self.line_for(crs.apply_push("claudecode/sonnet5", root, "pick",
                                            "project"))
        self.assertIn("commit failed there", line)
        self.assertIn(f"cd {root}", line)

    def test_a_kept_mask_is_reported_as_retryable(self):
        out = crs.ApplyOutcome(
            kind="commit_failed", wrote=True, mask_kept=True,
            reason=crs.REASON_DEST_COMMIT_UNAVAILABLE, detail="boom",
        )
        line = self.line_for(out)
        self.assertIn("local override was kept", line)
        self.assertIn("retry", line)


def _inprogress_states_from_shell() -> list[str]:
    """Read AIT_GIT_INPROGRESS_STATES out of lib/task_utils.sh.

    Read from the shell library rather than restated here, so this test walks
    the same set the production guard does. Restating it would make a dropped
    state pass on both sides at once.
    """
    import subprocess
    lib = REPO_ROOT / ".aitask-scripts" / "lib" / "task_utils.sh"
    out = subprocess.run(
        ["bash", "-c",
         f'SCRIPT_DIR="{REPO_ROOT}/.aitask-scripts" source "{lib}" >/dev/null 2>&1; '
         'printf "%s\\n" "${AIT_GIT_INPROGRESS_STATES[@]}"'],
        capture_output=True, text=True,
    )
    return [ln.strip() for ln in out.stdout.splitlines() if ln.strip()]


if __name__ == "__main__":
    unittest.main(verbosity=2)
