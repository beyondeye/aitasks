---
priority: low
effort: medium
depends: []
issue_type: refactor
status: Ready
labels: [git, bash_scripts, robustness, syncer]
gates: [risk_evaluated]
anchor: 1599
followup_kind: risk_mitigation
created_at: 2026-10-16 08:01
updated_at: 2026-10-16 08:01
---

## Origin

Risk-mitigation ("after") follow-up for t2024, created at Step 8d after implementation landed.

## Risk addressed

code-health — bounded-run implementations duplicated; sync/drift-check macOS fallback kills only the direct child

- `lib/bounded_run.py` is a fifth bounded-run implementation until sync, drift-check and github_release move onto it, and two of those still kill only the direct child on macOS · severity: low · → mitigation: consolidate_bounded_git_helpers

## Goal

t2024 added `.aitask-scripts/lib/bounded_run.py`, the framework's one tested runner for a network operation under a hard time bound:
- `run_bounded()` runs the command in a NEW SESSION (no controlling terminal), stdin `/dev/null`, output in temp files rather than pipes;
- on expiry it kills the whole process group (SIGTERM → SIGCONT → poll the group for a grace period → SIGKILL), and on a normal exit it never signals the group;
- signals arriving during cleanup are deferred and re-delivered afterwards;
- nested runners get strictly ordered graces via `AIT_BOUNDED_RUN_GRACE`;
- `noninteractive_env()` removes every prompt channel (`GIT_ASKPASS=""`, `GIT_TERMINAL_PROMPT=0`, `SSH_ASKPASS_REQUIRE=never`, `SSH_ASKPASS`/`DISPLAY`/`WAYLAND_DISPLAY` removed, `GCM_INTERACTIVE=never`);
- the CLI is `bounded_run.py --timeout N [--noninteractive] -- <cmd>`, exit 124 on timeout.

Move the older copies onto it:
- `.aitask-scripts/aitask_sync.sh:_git_with_timeout` (coreutils `timeout`, or a watchdog that kills only the direct child — the macOS fallback leaks transport descendants);
- `.aitask-scripts/aitask_remote_drift_check.sh:_git_fetch_with_timeout` (same shape);
- `.aitask-scripts/lib/github_release.sh:_github_ls_remote_tags` (set -m job + process-group kill; keeps the controlling terminal).

Constraints:
- `github_release.sh`'s tests stub `git` as a shell FUNCTION, which an exec'd helper would bypass (see its comment above `_github_ls_remote_tags`); keep that seam working.
- Keep each caller's exit-code contract (124 on timeout) and its own knob (`NETWORK_TIMEOUT`, `AIT_GIT_LSREMOTE_TIMEOUT`).
- `aitask_sync.sh`'s `_git_with_timeout` wraps `task_git`-style `-C <data worktree>` arguments.
- Decide per caller whether the non-interactive policy applies (sync pushes today use the user's terminal-less `timeout`, so it likely does).

Tests: reuse the TERM-ignoring grandchild fixture from `tests/test_bounded_run.py` / `tests/test_crew_publish_upstream.sh` (hang cells) and red-prove a direct-child-only kill on each migrated caller.
