#!/usr/bin/env python3
"""The syncer's main-branch pull / push against real git (t2126, t1791).

Every git output here is produced by real git in scratch repositories, run
through the syncer's own `run_git` (so under its pinned C locale): the
divergence classifier is fed what git actually prints, and the pull's
preconditions are exercised on real dirty, mid-merge and mid-rebase checkouts.
No Textual app is booted; the dialog wiring lives in test_syncer_rows.py.
"""
from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

PROJECT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_DIR / ".aitask-scripts" / "lib"))
sys.path.insert(0, str(PROJECT_DIR / ".aitask-scripts" / "syncer"))

import syncer_app  # noqa: E402
from sync_action_runner import build_main_conflict_prompt  # noqa: E402
from syncer_app import (  # noqa: E402
    MAIN_DIVERGED,
    MAIN_FAILED,
    MAIN_OK,
    MAIN_REFUSED,
    MAIN_SUBMODULES,
    classify_main_failure,
    run_git,
    run_main_pull,
    run_main_push,
)

_GIT_ENV = {
    "GIT_CONFIG_GLOBAL": os.devnull,
    "GIT_CONFIG_NOSYSTEM": "1",
    "GIT_AUTHOR_NAME": "t",
    "GIT_AUTHOR_EMAIL": "t@example.invalid",
    "GIT_COMMITTER_NAME": "t",
    "GIT_COMMITTER_EMAIL": "t@example.invalid",
    "GIT_TERMINAL_PROMPT": "0",
    # Submodules here are cloned over the file transport.
    "GIT_CONFIG_COUNT": "1",
    "GIT_CONFIG_KEY_0": "protocol.file.allow",
    "GIT_CONFIG_VALUE_0": "always",
}


def git(cwd: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess:
    """Fixture git (not the code under test): fails the test on error."""
    proc = subprocess.run(
        ["git", *args], cwd=cwd, capture_output=True, text=True,
        env={**os.environ, "LC_ALL": "C"},
    )
    if check and proc.returncode != 0:
        raise AssertionError(
            f"fixture git {args} failed ({proc.returncode}): {proc.stderr}")
    return proc


def rev(cwd: Path, ref: str) -> str:
    return git(cwd, "rev-parse", ref).stdout.strip()


def recording(after_fetch=None):
    """A GitRunner that records every call and can act right after the fetch."""
    calls: list[list[str]] = []

    def runner(args, cwd):
        calls.append(list(args))
        result = run_git(args, cwd)
        if args and args[0] == "fetch" and after_fetch is not None:
            after_fetch(Path(cwd))
        return result

    return runner, calls


class _ScratchRepos(unittest.TestCase):
    """A bare `origin`, a `seed` clone that plays "another machine", and
    clones under test. `ign` is gitignored from the first commit."""

    def setUp(self):
        env = mock.patch.dict(os.environ, _GIT_ENV)
        env.start()
        self.addCleanup(env.stop)
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.tmp = Path(tmp.name)
        self.remote = self.tmp / "remote.git"
        git(self.tmp, "init", "-q", "--bare", "-b", "main", str(self.remote))
        self.seed = self.tmp / "seed"
        git(self.tmp, "init", "-q", "-b", "main", str(self.seed))
        (self.seed / "f").write_text("base\n")
        (self.seed / ".gitignore").write_text("ign\n")
        git(self.seed, "add", ".")
        git(self.seed, "commit", "-qm", "base")
        git(self.seed, "remote", "add", "origin", str(self.remote))
        git(self.seed, "push", "-q", "-u", "origin", "main")

    def clone(self, name: str = "a") -> Path:
        path = self.tmp / name
        git(self.tmp, "clone", "-q", str(self.remote), str(path))
        return path

    def commit(self, repo: Path, name: str, content: str, *, force: bool = False):
        (repo / name).write_text(content)
        git(repo, "add", *(["-f"] if force else []), name)
        git(repo, "commit", "-qm", f"{name}: {content.strip()}")

    def advance_remote(self, name: str = "g", content: str = "remote\n", **kw):
        git(self.seed, "pull", "-q", "--ff-only")
        self.commit(self.seed, name, content, **kw)
        git(self.seed, "push", "-q", "origin", "main")

    def pull(self, repo: Path, branch: str = "main", runner=run_git):
        return run_main_pull(runner, str(repo), branch)


class DivergenceClassificationTests(_ScratchRepos):
    """Real git output in, the divergence verdict out. A classifier that
    never matches fails every positive here (the mutant check)."""

    def test_diverged_pull_opens_the_divergence_path(self):
        a = self.clone()
        self.advance_remote()
        self.commit(a, "h", "local\n")
        before = rev(a, "HEAD")

        result = self.pull(a)

        self.assertEqual(result.status, MAIN_DIVERGED, result.output)
        self.assertIn("Not possible to fast-forward", result.output)
        self.assertTrue(classify_main_failure("pull", "main", result.output))
        # Operation-specific: the push classifier does not read it.
        self.assertFalse(classify_main_failure("push", "main", result.output))
        self.assertIn("merge --ff-only", result.command)
        self.assertEqual(result.upstream, "origin/main")
        self.assertEqual(rev(a, "HEAD"), before)

    def test_push_fetch_first_rejection_is_divergence(self):
        a = self.clone()
        self.advance_remote()
        self.commit(a, "h", "local\n")

        result = run_main_push(run_git, str(a), "main")

        self.assertEqual(result.status, MAIN_DIVERGED, result.output)
        self.assertIn("(fetch first)", result.output)
        self.assertEqual(result.upstream, "origin/main")
        self.assertFalse(classify_main_failure("pull", "main", result.output))

    def test_push_non_fast_forward_rejection_is_divergence(self):
        a = self.clone()
        self.advance_remote()
        self.commit(a, "h", "local\n")
        git(a, "fetch", "-q")

        result = run_main_push(run_git, str(a), "main")

        self.assertEqual(result.status, MAIN_DIVERGED, result.output)
        self.assertIn("(non-fast-forward)", result.output)
        # Anchored to the ref that was pushed.
        self.assertFalse(classify_main_failure("push", "develop", result.output))

    def test_hook_rejected_push_is_a_plain_failure(self):
        hook = self.remote / "hooks" / "pre-receive"
        hook.write_text("#!/bin/sh\nexit 1\n")
        hook.chmod(0o755)
        a = self.clone()
        self.commit(a, "h", "local\n")

        result = run_main_push(run_git, str(a), "main")

        self.assertEqual(result.status, MAIN_FAILED, result.output)
        self.assertIn("[remote rejected]", result.output)
        self.assertFalse(classify_main_failure("push", "main", result.output))

    def test_push_to_an_unreachable_remote_is_a_plain_failure(self):
        a = self.clone()
        git(a, "remote", "set-url", "origin", str(self.tmp / "missing.git"))
        self.commit(a, "h", "local\n")

        result = run_main_push(run_git, str(a), "main")

        self.assertEqual(result.status, MAIN_FAILED, result.output)
        self.assertFalse(classify_main_failure("push", "main", result.output))

    def test_overwrite_refusal_is_not_divergence(self):
        a = self.clone()
        (a / "g").write_text("mine, untracked\n")
        self.advance_remote("g", "theirs\n")

        result = self.pull(a)

        self.assertEqual(result.status, MAIN_FAILED, result.output)
        self.assertIn("would be overwritten", result.output)
        self.assertFalse(classify_main_failure("pull", "main", result.output))
        self.assertEqual((a / "g").read_text(), "mine, untracked\n")

    def test_unknown_action_is_never_divergence(self):
        self.assertFalse(classify_main_failure(
            "sync", "main", "fatal: Not possible to fast-forward, aborting.\n"))


class PullPreconditionTests(_ScratchRepos):
    """t1791: git decides about dirty files; only a mid-operation checkout is
    refused up front."""

    def test_unrelated_dirty_file_is_left_untouched(self):
        a = self.clone()
        git(a, "config", "merge.autoStash", "true")
        (a / "f").write_text("dirty, uncommitted\n")
        inode = (a / "f").stat().st_ino
        self.advance_remote()

        result = self.pull(a)

        self.assertEqual(result.status, MAIN_OK, result.output)
        self.assertEqual(rev(a, "HEAD"), rev(self.seed, "HEAD"))
        self.assertEqual((a / "f").read_text(), "dirty, uncommitted\n")
        # --no-autostash: not stashed and re-applied (which rewrites the file).
        self.assertEqual((a / "f").stat().st_ino, inode)

    def test_remote_change_to_the_dirty_file_is_refused_naming_it(self):
        a = self.clone()
        (a / "f").write_text("dirty, uncommitted\n")
        self.advance_remote("f", "theirs\n")
        before = rev(a, "HEAD")

        result = self.pull(a)

        self.assertEqual(result.status, MAIN_FAILED, result.output)
        self.assertIn("would be overwritten", result.output)
        self.assertIn("\tf\n", result.output)
        self.assertEqual((a / "f").read_text(), "dirty, uncommitted\n")
        self.assertEqual(rev(a, "HEAD"), before)

    def test_ignored_local_file_is_never_overwritten(self):
        a = self.clone()
        (a / "ign").write_text("local, ignored\n")
        self.advance_remote("ign", "theirs\n", force=True)

        result = self.pull(a)

        self.assertEqual(result.status, MAIN_FAILED, result.output)
        self.assertIn("ign", result.output)
        self.assertEqual((a / "ign").read_text(), "local, ignored\n")

    def _conflicting_side_branch(self, a: Path) -> None:
        git(a, "checkout", "-q", "-b", "side")
        self.commit(a, "f", "side\n")
        git(a, "checkout", "-q", "main")
        self.commit(a, "f", "main\n")

    def test_mid_merge_is_refused_before_anything_runs(self):
        a = self.clone()
        self._conflicting_side_branch(a)
        self.assertNotEqual(git(a, "merge", "side", check=False).returncode, 0)
        runner, calls = recording()

        result = self.pull(a, runner=runner)

        self.assertEqual(result.status, MAIN_REFUSED)
        self.assertIn("mid-merge", result.message)
        self.assertEqual([c for c in calls if c[0] in ("fetch", "merge")], [])

    def test_mid_rebase_is_refused_before_anything_runs(self):
        a = self.clone()
        self._conflicting_side_branch(a)
        self.assertNotEqual(git(a, "rebase", "side", check=False).returncode, 0)
        runner, calls = recording()

        result = self.pull(a, runner=runner)

        self.assertEqual(result.status, MAIN_REFUSED)
        self.assertEqual([c for c in calls if c[0] in ("fetch", "merge")], [])

    def test_other_branch_checked_out_is_refused(self):
        a = self.clone()
        git(a, "checkout", "-q", "-b", "feature")

        result = self.pull(a)

        self.assertEqual(result.status, MAIN_REFUSED)
        self.assertIn("currently on feature", result.message)

    def test_no_upstream_is_a_plain_failure(self):
        a = self.clone()
        git(a, "checkout", "-q", "-b", "topic")

        result = self.pull(a, branch="topic")

        self.assertEqual(result.status, MAIN_FAILED)
        self.assertIn("no upstream", result.output)


class PullBindingTests(_ScratchRepos):
    """The fetch -> pin -> merge sequence keeps what one `git pull` guaranteed:
    it applies to the named branch only, and only what this fetch proved."""

    def test_branch_switch_during_fetch_merges_nothing(self):
        a = self.clone()
        git(a, "branch", "feature")          # an older main: fast-forwardable
        self.advance_remote()
        main_before, feature_before = rev(a, "main"), rev(a, "feature")
        runner, calls = recording(
            after_fetch=lambda cwd: git(cwd, "checkout", "-q", "feature"))

        result = self.pull(a, runner=runner)

        self.assertEqual(result.status, MAIN_REFUSED)
        self.assertIn("changed while fetching", result.message)
        self.assertEqual(rev(a, "refs/heads/feature"), feature_before)
        self.assertEqual(rev(a, "refs/heads/main"), main_before)
        self.assertFalse(any(c[0] == "merge" for c in calls))
        # The guard is what stopped it: the pinned commit WOULD fast-forward
        # feature, so an unguarded merge would have moved the wrong branch.
        self.assertEqual(git(a, "merge-base", "--is-ancestor", "feature",
                             "origin/main", check=False).returncode, 0)

    def test_merge_started_during_fetch_merges_nothing(self):
        a = self.clone()
        PullPreconditionTests._conflicting_side_branch(self, a)
        self.advance_remote()
        runner, calls = recording(
            after_fetch=lambda cwd: git(cwd, "merge", "side", check=False))

        result = self.pull(a, runner=runner)

        self.assertEqual(result.status, MAIN_REFUSED)
        self.assertIn("mid-merge", result.message)
        self.assertFalse(any(c[:2] == ["merge", "--ff-only"] for c in calls))

    def test_deleted_remote_branch_fails_instead_of_using_the_stale_ref(self):
        a = self.clone()
        self.advance_remote()
        git(a, "fetch", "-q")
        git(self.remote, "update-ref", "-d", "refs/heads/main")
        # Control: a plain non-pruning fetch exits 0 and keeps the stale ref —
        # why the pull fetches the upstream ref by name.
        self.assertEqual(git(a, "fetch", check=False).returncode, 0)
        self.assertEqual(git(a, "rev-parse", "--verify", "-q", "origin/main",
                             check=False).returncode, 0)
        before = rev(a, "HEAD")

        result = self.pull(a)

        self.assertEqual(result.status, MAIN_FAILED)
        self.assertIn("couldn't find remote ref", result.output)
        self.assertEqual(rev(a, "HEAD"), before)

    def test_tracking_ref_disagreeing_with_the_fetch_merges_nothing(self):
        a = self.clone()
        old = rev(a, "HEAD")
        self.advance_remote()
        runner, calls = recording(
            after_fetch=lambda cwd: git(
                cwd, "update-ref", "refs/remotes/origin/main", old))

        result = self.pull(a, runner=runner)

        self.assertEqual(result.status, MAIN_FAILED)
        self.assertIn("does not match what this fetch brought", result.output)
        self.assertEqual(rev(a, "HEAD"), old)
        self.assertFalse(any(c[0] == "merge" for c in calls))

    def test_the_named_branchs_configured_upstream_is_used(self):
        a = self._release_upstream()
        runner, calls = recording()

        result = self.pull(a, runner=runner)

        self.assertEqual(result.status, MAIN_OK, result.output)
        self.assertEqual(rev(a, "HEAD"), rev(self.seed, "release"))
        self.assertEqual(result.upstream, "origin/release")
        self.assertIn(["fetch", "origin", "refs/heads/release"], calls)


    def _release_upstream(self) -> Path:
        """`a`'s main tracks origin/release, a branch main does not contain."""
        git(self.seed, "push", "-q", "origin", "main:release")
        git(self.seed, "checkout", "-q", "-b", "release")
        self.commit(self.seed, "r", "release only\n")
        git(self.seed, "push", "-q", "origin", "release")
        git(self.seed, "checkout", "-q", "main")
        a = self.clone()
        git(a, "config", "branch.main.merge", "refs/heads/release")
        return a

    def test_divergence_from_a_differently_named_upstream_names_it(self):
        a = self._release_upstream()
        self.commit(a, "h", "local\n")
        # main already contains origin/main: only the release divergence is real.
        git(a, "fetch", "-q")
        self.assertEqual(git(a, "merge-base", "--is-ancestor", "origin/main",
                             "main", check=False).returncode, 0)

        result = self.pull(a)

        self.assertEqual(result.status, MAIN_DIVERGED, result.output)
        self.assertEqual(result.upstream, "origin/release")
        # git's refusal does not name it, so the agent must be told.
        self.assertNotIn("release", result.output)
        prompt = build_main_conflict_prompt(
            "pull", MAIN_DIVERGED, "main", result.upstream, a, result.output)
        self.assertIn("integrate the local `main` with `origin/release`", prompt)
        self.assertNotIn("origin/main", prompt)


class SubmoduleDeferralTests(_ScratchRepos):
    """Deliberately narrow (t2126): with submodule.recurse set, `git pull`
    would also update the submodules, so when the checkout has initialized
    submodules the syncer defers to the resolver agent before changing
    anything. Without either condition the ordinary pull runs."""

    def setUp(self):
        super().setUp()
        dep_remote = self.tmp / "dep.git"
        git(self.tmp, "init", "-q", "--bare", "-b", "main", str(dep_remote))
        work = self.tmp / "depwork"
        git(self.tmp, "init", "-q", "-b", "main", str(work))
        self.commit(work, "d", "d1\n")
        git(work, "push", "-q", str(dep_remote), "main")
        git(self.seed, "submodule", "add", "-q", str(dep_remote), "dep")
        git(self.seed, "commit", "-qm", "add dep")
        git(self.seed, "push", "-q", "origin", "main")

    def clone(self, name: str = "a", *, recurse: bool = True,
              init: bool = True) -> Path:
        path = self.tmp / name
        git(self.tmp, "clone", "-q", *(["--recurse-submodules"] if init else []),
            str(self.remote), str(path))
        if recurse:
            git(path, "config", "submodule.recurse", "true")
        return path

    def bump_dep(self) -> str:
        sub = self.seed / "dep"
        self.commit(sub, "d", "d2\n")
        git(sub, "push", "-q", "origin", "HEAD:main")
        git(self.seed, "commit", "-qam", "bump dep")
        git(self.seed, "push", "-q", "origin", "main")
        return rev(sub, "HEAD")

    def state(self, a: Path) -> tuple[str, str, str, str]:
        return (rev(a, "HEAD"), rev(a, "refs/remotes/origin/main"),
                rev(a / "dep", "HEAD"),
                git(a, "status", "--porcelain", "--ignore-submodules=none").stdout)

    def test_recursive_submodules_defer_before_changing_anything(self):
        a = self.clone()
        before = self.state(a)
        self.bump_dep()
        runner, calls = recording()

        result = self.pull(a, runner=runner)

        self.assertEqual(result.status, MAIN_SUBMODULES)
        self.assertEqual(result.upstream, "origin/main")
        self.assertEqual(self.state(a), before)
        self.assertFalse(any(c[0] in ("fetch", "merge", "submodule") for c in calls))

    def test_a_submodule_url_from_an_included_config_still_defers(self):
        # Initialized as far as git is concerned: the url only moved into a
        # file .git/config includes.
        a = self.clone()
        url = git(a, "config", "--local", "submodule.dep.url").stdout.strip()
        git(a, "config", "--local", "--unset", "submodule.dep.url")
        gitdir = Path(git(a, "rev-parse", "--absolute-git-dir").stdout.strip())
        (gitdir / "submodules.inc").write_text(f'[submodule "dep"]\n\turl = {url}\n')
        git(a, "config", "--local", "include.path", "submodules.inc")
        self.assertEqual(git(a, "config", "submodule.dep.url").stdout.strip(), url)
        before = self.state(a)
        self.bump_dep()
        runner, calls = recording()

        result = self.pull(a, runner=runner)

        self.assertEqual(result.status, MAIN_SUBMODULES)
        self.assertEqual(self.state(a), before)
        self.assertFalse(any(c[0] in ("fetch", "merge", "submodule") for c in calls))

    def test_the_deferral_names_a_differently_named_upstream(self):
        git(self.seed, "push", "-q", "origin", "main:release")
        a = self.clone()
        git(a, "config", "branch.main.merge", "refs/heads/release")

        result = self.pull(a)

        self.assertEqual(result.status, MAIN_SUBMODULES)
        self.assertEqual(result.upstream, "origin/release")

    def test_without_submodule_recurse_the_ordinary_pull_runs(self):
        # `git pull` would not touch the submodule either.
        a = self.clone(recurse=False)
        old = rev(a / "dep", "HEAD")
        self.bump_dep()

        result = self.pull(a)

        self.assertEqual(result.status, MAIN_OK, result.output)
        self.assertEqual(rev(a, "HEAD"), rev(self.seed, "HEAD"))
        self.assertEqual(rev(a / "dep", "HEAD"), old)

    def test_uninitialized_submodules_do_not_defer(self):
        a = self.clone(init=False)
        self.bump_dep()

        result = self.pull(a)

        self.assertEqual(result.status, MAIN_OK, result.output)
        self.assertEqual(rev(a, "HEAD"), rev(self.seed, "HEAD"))

    def test_an_unreadable_submodule_recurse_value_fails_closed(self):
        a = self.clone()
        git(a, "config", "submodule.recurse", "sometimes")
        head = rev(a, "HEAD")
        self.bump_dep()

        result = self.pull(a)

        self.assertEqual(result.status, MAIN_FAILED)
        self.assertEqual(rev(a, "HEAD"), head)


class RunGitLocaleTests(unittest.TestCase):
    def test_git_runs_with_a_pinned_c_locale(self):
        seen = {}

        def fake_run(argv, **kwargs):
            seen.update(kwargs["env"])
            return subprocess.CompletedProcess(argv, 0, "", "")

        with mock.patch.dict(os.environ, {"LC_ALL": "de_DE.UTF-8",
                                          "LANGUAGE": "de"}), \
                mock.patch.object(syncer_app.subprocess, "run", fake_run):
            run_git(["status"], ".")
        self.assertEqual(seen["LC_ALL"], "C")
        self.assertNotIn("LANGUAGE", seen)


if __name__ == "__main__":
    unittest.main()
