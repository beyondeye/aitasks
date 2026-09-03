"""Settings TUI saves commit the project-layer config they wrote (t1677).

`aitasks/metadata/*` has no derivable task id, so `ait sync`'s sweep refuses to
attribute it (t1599_3) -- correctly, since sweeping it in is what left
`board_config.json` with 8 of its 9 commits under unrelated tasks' messages. But
nothing else committed those files either, so an ownerless dirty config became a
**permanent** rebase deferral. A Settings save now owns what it wrote.

What is pinned here, and why each case exists:

* the **project** layer is committed, path-scoped, named after the file;
* the **user** layer (`*.local.json`, gitignored) commits nothing -- the
  "incidental save must not commit" half of the amended convention;
* a **new project profile** is committed. `_handle_new_profile` reaches
  `save_profile` with a project-layer name that does not exist yet, so a
  tracked-only helper would refuse it as untracked and leave an ordinary
  Settings creation dirty. `save_profile` derives `allow_new` from an existence
  check taken BEFORE its write -- only the writer can tell create from update;
* a **failed** commit returns `failed`, leaves the edit on disk, and still
  fires `on_commit`, so the error notification is reachable rather than merely
  possible. A swallowed failure recreates the exact defect.

Unlike the other settings tests, the fixture is a real git repo in the
production branch-mode topology (`.aitask-data` + an `aitasks` symlink) -- there
is nothing to assert about committing without one.

Run: python3 tests/test_settings_commit_on_save.py
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / ".aitask-scripts"))
sys.path.insert(0, str(REPO_ROOT / ".aitask-scripts" / "lib"))
sys.path.insert(0, str(REPO_ROOT / ".aitask-scripts" / "settings"))

import keybinding_registry  # noqa: E402
from shortcuts_mixin import refresh_label_case  # noqa: E402
from metadata_commit import remedy_command  # noqa: E402
from settings_app import METADATA_DIR, ConfigManager, SettingsApp, _repo_rel  # noqa: E402

_GIT_ENV = {
    "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t",
    "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t",
    "GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_SYSTEM": os.devnull,
}

_IGNORES = (
    "aitasks/metadata/userconfig.yaml\n"
    "aitasks/metadata/*.local.json\n"
    "aitasks/metadata/profiles/local/\n"
)


def _git(tree: Path, *args: str) -> str:
    """Run git in the fixture's data worktree and return stdout."""
    return subprocess.run(
        ["git", "-C", str(tree / ".aitask-data"), *args],
        capture_output=True, text=True, env={**os.environ, **_GIT_ENV},
    ).stdout.strip()


class _Fixture(unittest.TestCase):
    """A branch-mode repo the Settings TUI can actually commit into."""

    def setUp(self) -> None:
        keybinding_registry._reset_for_tests()
        refresh_label_case()
        self._prev_cwd = os.getcwd()
        self._tmp = tempfile.TemporaryDirectory(prefix="ait_settings_commit_")
        self.addCleanup(self._tmp.cleanup)
        self.tree = Path(self._tmp.name) / "tree"

        data = self.tree / ".aitask-data"
        meta = data / "aitasks" / "metadata"
        (meta / "profiles").mkdir(parents=True)
        (data / ".gitignore").write_text(_IGNORES, encoding="utf-8")
        (meta / "board_config.json").write_text(
            json.dumps({"columns": [], "column_order": []}), encoding="utf-8")
        (meta / "codeagent_config.json").write_text(
            json.dumps({"defaults": {}}), encoding="utf-8")
        (meta / "project_config.yaml").write_text("verify_build: true\n", encoding="utf-8")
        (meta / "profiles" / "fast.yaml").write_text("name: fast\n", encoding="utf-8")
        (self.tree / "aitasks").symlink_to(Path(".aitask-data") / "aitasks")

        env = {**os.environ, **_GIT_ENV}
        subprocess.run(["git", "init", "-q", "-b", "main", "."],
                       cwd=data, env=env, check=True)
        subprocess.run(["git", "add", "-A", "."], cwd=data, env=env, check=True)
        subprocess.run(["git", "commit", "-q", "--no-verify", "-m", "fixture"],
                       cwd=data, env=env, check=True)

        # The helper is invoked as ./.aitask-scripts/... relative to cwd.
        # Deliberately NOT a symlink to the whole real .aitask-scripts: other
        # helpers resolve their own paths off SCRIPT_DIR, so a save that shells
        # out (save_profile re-renders skill closures) would reach into the real
        # repository. Expose only the one script under test, with lib/ linked
        # for its two `source` lines.
        scripts = self.tree / ".aitask-scripts"
        scripts.mkdir()
        (scripts / "lib").symlink_to(REPO_ROOT / ".aitask-scripts" / "lib")
        shutil.copy2(
            REPO_ROOT / ".aitask-scripts" / "aitask_metadata_commit.sh",
            scripts / "aitask_metadata_commit.sh",
        )
        os.chdir(self.tree)
        self.addCleanup(os.chdir, self._prev_cwd)

    # --- helpers ---------------------------------------------------------
    def head_subject(self) -> str:
        return _git(self.tree, "log", "-1", "--format=%s")

    def head_files(self) -> list[str]:
        out = _git(self.tree, "show", "--name-only", "--format=", "HEAD")
        return [ln for ln in out.splitlines() if ln.strip()]

    def head_sha(self) -> str:
        return _git(self.tree, "rev-parse", "HEAD")

    def porcelain(self) -> str:
        return _git(self.tree, "status", "--porcelain")

    def is_tracked(self, rel: str) -> bool:
        return subprocess.run(
            ["git", "-C", str(self.tree / ".aitask-data"),
             "ls-files", "--error-unmatch", "--", rel],
            capture_output=True, env={**os.environ, **_GIT_ENV},
        ).returncode == 0

    def fail_next_commit(self) -> None:
        """Make `git commit` fail via the documented pre-commit-hook seam.

        Same mechanism and reasoning as tests/test_fold_mark.sh:337 -- no commit
        site passes --no-verify, and git releases the index lock on hook
        failure, so the index stays inspectable afterwards.
        """
        hooks = self.tree / ".aitask-data" / ".git" / "hooks"
        hooks.mkdir(parents=True, exist_ok=True)
        hook = hooks / "pre-commit"
        hook.write_text("#!/bin/sh\nexit 1\n", encoding="utf-8")
        hook.chmod(0o755)

    def manager(self):
        mgr = ConfigManager()
        self.calls = []
        mgr.on_commit = lambda result, paths: self.calls.append((result, paths))
        return mgr


class ProjectLayerCommits(_Fixture):

    def test_project_config_save_commits_that_file_only(self):
        mgr = self.manager()
        mgr.save_project_settings({"verify_build": "make check"})

        self.assertEqual(self.head_subject(), "ait: Update project_config.yaml")
        self.assertEqual(self.head_files(), ["aitasks/metadata/project_config.yaml"])
        self.assertEqual(self.porcelain(), "")
        self.assertEqual(self.calls[-1][0].status, "committed")

    def test_codeagent_save_commits_the_project_layer_and_skips_the_local_one(self):
        mgr = self.manager()
        mgr.save_codeagent({"defaults": {"plan": "claudecode"}}, {"defaults": {}})

        self.assertEqual(self.head_subject(), "ait: Update codeagent_config.json")
        self.assertEqual(self.head_files(), ["aitasks/metadata/codeagent_config.json"])
        # The user layer was written too and is gitignored -- it must not appear.
        self.assertTrue(
            (self.tree / "aitasks/metadata/codeagent_config.local.json").is_file())
        self.assertNotIn("codeagent_config.local.json", self.porcelain())

    def test_a_bystander_dirty_file_does_not_ride_along(self):
        (self.tree / "aitasks" / "metadata" / "board_config.json").write_text(
            json.dumps({"columns": [{"id": "x"}], "column_order": ["x"]}),
            encoding="utf-8")
        mgr = self.manager()
        mgr.save_project_settings({"verify_build": "make check"})

        self.assertEqual(self.head_files(), ["aitasks/metadata/project_config.yaml"])
        self.assertIn("board_config.json", self.porcelain())

    def test_saving_an_unchanged_config_commits_nothing(self):
        before = self.head_sha()
        mgr = self.manager()
        mgr.save_project_settings({"verify_build": True})
        self.assertEqual(self.head_sha(), before)
        self.assertEqual(self.calls[-1][0].status, "nochange")


class ProfileCreation(_Fixture):
    """The `_handle_new_profile` path: save_profile CREATES as well as updates."""

    def test_a_new_project_profile_is_tracked_and_committed(self):
        mgr = self.manager()
        mgr.save_profile("brandnew.yaml", {"name": "brandnew"}, layer="project")

        self.assertEqual(self.head_subject(), "ait: Update brandnew.yaml")
        self.assertTrue(self.is_tracked("aitasks/metadata/profiles/brandnew.yaml"))
        self.assertEqual(self.porcelain(), "")
        self.assertEqual(self.calls[-1][0].status, "committed")

    def test_a_new_user_profile_is_skipped_not_committed(self):
        before = self.head_sha()
        mgr = self.manager()
        mgr.save_profile("mine.yaml", {"name": "mine"}, layer="user")

        self.assertTrue(
            (self.tree / "aitasks/metadata/profiles/local/mine.yaml").is_file())
        self.assertEqual(self.head_sha(), before)
        self.assertEqual(self.calls[-1][0].status, "skipped")

    def test_updating_an_existing_project_profile_commits(self):
        mgr = self.manager()
        mgr.save_profile("fast.yaml", {"name": "fast", "record_gates": True},
                         layer="project")
        self.assertEqual(self.head_subject(), "ait: Update fast.yaml")
        self.assertEqual(self.head_files(), ["aitasks/metadata/profiles/fast.yaml"])

    def test_deleting_a_tracked_profile_commits_the_deletion(self):
        mgr = self.manager()
        mgr.profile_layers["fast.yaml"] = "project"
        mgr.delete_profile("fast.yaml")

        self.assertEqual(self.head_subject(), "ait: Update fast.yaml")
        self.assertFalse(self.is_tracked("aitasks/metadata/profiles/fast.yaml"))
        self.assertEqual(self.porcelain(), "")

    def test_deleting_a_profile_drops_it_from_the_in_memory_maps(self):
        """The commit must not short-circuit the bookkeeping that follows it.

        `delete_profile` ends in `return self._commit(...)`, so anything placed
        after that return is dead code -- and the live Settings UI would keep
        offering a profile whose file is gone until a full reload.
        """
        mgr = self.manager()
        mgr.profile_layers["fast.yaml"] = "project"
        mgr.profiles.setdefault("fast.yaml", {"name": "fast"})
        mgr.delete_profile("fast.yaml")

        self.assertNotIn("fast.yaml", mgr.profiles)
        self.assertNotIn("fast.yaml", mgr.profile_layers)


class CommitFailureIsReported(_Fixture):
    """A swallowed failure is the whole defect -- it must reach a caller."""

    def test_failure_keeps_the_edit_and_still_fires_on_commit(self):
        self.fail_next_commit()
        before = self.head_sha()
        mgr = self.manager()
        mgr.save_project_settings({"verify_build": "make check"})

        result, paths = self.calls[-1]
        self.assertEqual(result.status, "failed")
        self.assertEqual(paths, ["aitasks/metadata/project_config.yaml"])
        self.assertEqual(self.head_sha(), before, "nothing may be committed")
        # The write already landed; losing it to a commit error would be worse
        # than a dirty file.
        self.assertIn(
            "make check",
            (self.tree / "aitasks/metadata/project_config.yaml").read_text())

    def test_failure_leaves_nothing_of_ours_staged(self):
        self.fail_next_commit()
        mgr = self.manager()
        # A created path is the only one the helper stages, so it is the one
        # that could be left behind for an index-wide commit to swallow.
        mgr.save_profile("ghost.yaml", {"name": "ghost"}, layer="project")

        self.assertEqual(self.calls[-1][0].status, "failed")
        staged = _git(self.tree, "diff", "--cached", "--name-only")
        self.assertNotIn("ghost.yaml", staged)
        self.assertFalse(self.is_tracked("aitasks/metadata/profiles/ghost.yaml"))


class RemedyMatchesTheAdmission(_Fixture):
    """A failed commit must advertise a remedy that actually works.

    The helper's failure path unstages exactly the entries it staged, so a file
    this run CREATED is left untracked. A remedy rendered without `--allow-new`
    then answers `REFUSED:untracked` and clears nothing -- worse than no advice,
    because the user concludes the file cannot be committed at all.
    """

    def test_a_failed_new_profile_carries_allow_new_on_the_result(self):
        self.fail_next_commit()
        mgr = self.manager()
        mgr.save_profile("brandnew.yaml", {"name": "brandnew"}, layer="project")

        result, paths = self.calls[-1]
        self.assertEqual(result.status, "failed")
        # Fails against a CommitResult that does not carry the admission.
        self.assertTrue(result.allow_new)
        self.assertIn("--allow-new", remedy_command(paths, allow_new=result.allow_new))

    def test_an_existing_file_failure_does_not_advertise_allow_new(self):
        """The other direction: the flag must not become unconditional."""
        self.fail_next_commit()
        mgr = self.manager()
        mgr.save_profile("fast.yaml", {"name": "fast", "record_gates": True},
                         layer="project")

        result, paths = self.calls[-1]
        self.assertEqual(result.status, "failed")
        self.assertFalse(result.allow_new)
        self.assertNotIn("--allow-new", remedy_command(paths, allow_new=result.allow_new))

    def test_the_advertised_remedy_actually_commits_the_file(self):
        """The assertion that matters: run the exact string the user is shown."""
        self.fail_next_commit()
        mgr = self.manager()
        mgr.save_profile("brandnew.yaml", {"name": "brandnew"}, layer="project")
        result, paths = self.calls[-1]
        cmd = remedy_command(paths, allow_new=result.allow_new)

        rel = "aitasks/metadata/profiles/brandnew.yaml"
        self.assertFalse(self.is_tracked(rel))
        (self.tree / ".aitask-data" / ".git" / "hooks" / "pre-commit").unlink()

        proc = subprocess.run(cmd, shell=True, cwd=self.tree,
                              capture_output=True, text=True,
                              env={**os.environ, **_GIT_ENV})
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertTrue(self.is_tracked(rel))


class ImportAdmissionIsPerPath(_Fixture):
    """`allow_new` is a per-path permission, not a batch mode.

    An import that creates one config while overwriting a pre-existing
    *untracked* one must admit only the first. One boolean for the batch
    publishes local content the import merely overwrote.
    """

    def _app(self):
        app = SettingsApp()
        self.notified = []
        app._notify_commit = lambda result, paths: self.notified.append((result, paths))
        return app

    def _run_mixed_import(self):
        meta = self.tree / ".aitask-data" / "aitasks" / "metadata"
        # Untracked local content that ALREADY existed before the import.
        (meta / "stray_local.json").write_text('{"a": 1}', encoding="utf-8")
        pre_existing = {_repo_rel(q) for q in METADATA_DIR.glob("*")}
        # The import overwrites that one and creates a genuinely new one.
        (meta / "stray_local.json").write_text('{"a": 2}', encoding="utf-8")
        (meta / "imported_new.json").write_text('{"b": 1}', encoding="utf-8")

        self._app()._commit_imported(
            ["imported_new.json", "stray_local.json"], pre_existing)

    def test_only_the_created_config_is_admitted(self):
        self._run_mixed_import()

        self.assertTrue(self.is_tracked("aitasks/metadata/imported_new.json"))
        # Fails against a single batch-wide `created_any` boolean.
        self.assertFalse(self.is_tracked("aitasks/metadata/stray_local.json"))

    def test_the_overwritten_file_is_refused_not_silently_dropped(self):
        """A refusal the user never sees is the ownerless-file state again."""
        self._run_mixed_import()

        statuses = {r.status for r, _ in self.notified}
        self.assertIn("committed", statuses)
        self.assertIn("refused", statuses)

    def test_the_pre_existing_edit_survives_on_disk(self):
        self._run_mixed_import()
        meta = self.tree / ".aitask-data" / "aitasks" / "metadata"
        self.assertEqual(meta / "stray_local.json" and
                         (meta / "stray_local.json").read_text(), '{"a": 2}')


if __name__ == "__main__":
    unittest.main(verbosity=2)
