---
priority: low
effort: medium
depends: []
issue_type: bug
status: Implementing
labels: [git, bash_scripts, robustness, syncer]
gates: [risk_evaluated]
assigned_to: dario-e@beyond-eye.com
anchor: 1599
followup_kind: risk_mitigation
created_at: 2026-10-16 01:06
updated_at: 2026-10-20 17:23
---

## Origin

Risk-mitigation ("after") follow-up for t2018, created at Step 8d after implementation landed.

## Risk addressed

goal-achievement — content conflict on _runner_alive.yaml is deferred, not converged

- A true content conflict on `_runner_alive.yaml` (adjacent-line edits since the merge
  base: a runner restarted with a new `interval` while a remote stop is pending, or a
  takeover runner rewriting the file) is deferred on each iteration, not converged; the
  remote stop stays unseen until resolved by hand. Outside "a file the runner
  dirtied", but reachable · severity: low · → mitigation:
  crew_runner_alive_conflict_convergence

## Goal

Converge a conflicted runner pull on `_runner_alive.yaml` instead of deferring it forever.

After t2018 (commit ab2cf4b37), `git_pull` in `.aitask-scripts/agentcrew/agentcrew_utils.py` proves a diverged merge clean in memory (`merge-tree --write-tree`), then fast-forwards to it with a protected `merge --ff-only --no-overwrite-ignore`. When `merge-tree` reports a conflict, the pull is deferred (`merge_conflict: <paths>`) and nothing is written. When the only conflicted path is the runner's own `_runner_alive.yaml`, the runner owns the file and knows how each side's fields should combine:
- keep the incoming `requested_action` (a remote stop must win);
- keep the runner's own identity and heartbeat fields (`status`, `pid`, `hostname`, `started_at`, `last_heartbeat`, `next_check_at`, `interval`), which it rewrites after the pull anyway.

Build the resolved blob in memory, never in the live worktree. For example: read both sides' YAML with `git show`, merge field-wise, `hash-object -w`, then build the merged tree from merge-tree's result plus that blob and `commit-tree` it (signed per `commit.gpgSign`, as `_merge_diverged` does). Advance with the same `_advance()`. Any other conflicted path, or an unparseable side, keeps today's deferral.

Constraints carried over from t2018: never open a merge or write conflict markers in the live crew worktree; never stash, rewrite or revert another process's uncommitted file; `--no-autostash` stays. Extend `tests/test_crew_pull_no_autostash.sh`, whose harness already drives `git_pull` and `run_loop`. Turn the conflict scenario from cell 8 (but on `_runner_alive.yaml`: a local `interval: 60` commit plus a peer `requested_action: stop`) into a convergence cell: the stop is honoured, the push converges, and the merge commit carries the resolved fields.

## Inbox
<!-- Appended by the note framework. Do not edit by hand; use `./ait note`. -->

> **✉ note:t2024** id=2026-10-16T05:02:57Z.08fcd57fba5492cdf769fc9c from=t2024 from_verified=yes at=2026-10-16T05:02:57Z base=989687394d156e04d8cd8a58ae71735104b56ab6 base_branch=main dirty=no host=omg16
>
> | t2024 (commit ae0074ab7) changed the harness and the pull your task builds on. Refs as of that commit:
> | 
> | - `agentcrew_utils.git_cmd` gained a `timeout=` keyword (`agentcrew_utils.py:317`). With it, the command runs through `lib/bounded_run.run_bounded` (new session, process-group kill) under a non-interactive environment, and a timeout returns rc 124. `_sync_with_upstream`'s fetch (line 475) and `git_push` now pass `timeout=crew_git_timeout()` (`AIT_CREW_GIT_TIMEOUT`, default 10s). A timed-out fetch defers as `fetch_failed: timed out after Ns ...`.
> | - `tests/test_crew_pull_no_autostash.sh` harness: `wrapped_git_cmd(worktree, *a, check=True, **kw)` (line 168) now forwards `**kw`. If you add another wrapper, keep the `**kw` or the bounded fetch raises TypeError.
> | - The harness's fake sleep is now scoped to the runner module (`r.time = types.SimpleNamespace(...)`, line 280). Replacing `time.sleep` globally also replaced the one `Popen.wait(timeout)` polls with inside `run_bounded`, and the 600-call cap tripped on every iteration. Patch `r.time`, never the global module.
> | 
> | Advisory context only.

> **✉ note:t2035** id=2026-10-19T09:54:18Z.17e1f0eff5796b70ddf362fa from=t2035 from_verified=yes at=2026-10-19T09:54:18Z base=245754abee80860da3e66b62a3b955fb27a7fb92 base_branch=main dirty=yes host=omg16
>
> | Advisory, from t2035 (commit 245754abe): the claim in this task's body that git_cmd(timeout=) runs through bounded_run in a 'new session' is now conditional. lib/bounded_run.py's _child_isolation() uses a new session only when the runner has a controlling terminal; otherwise git leads its own process group inside the caller's session. The process-group kill, the rc 124 on timeout and the non-interactive environment are unchanged, so this probably does not affect your premise. It is noted so the wording is not relied on.

> **👁 note:read** id=2026-10-20T14:23:18Z.ff641d93d02cff237e5d3d0f by=t2029 at=2026-10-20T14:23:18Z mode=explicit ids=2026-10-16T05:02:57Z.08fcd57fba5492cdf769fc9c,2026-10-19T09:54:18Z.17e1f0eff5796b70ddf362fa
