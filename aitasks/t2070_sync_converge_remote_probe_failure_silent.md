---
priority: medium
effort: low
depends: []
issue_type: bug
status: Implementing
labels: [git, bash_scripts, robustness]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
anchor: 1599
followup_kind: upstream_defect
implemented_with: claudecode/opus5_5
created_at: 2026-10-19 17:28
updated_at: 2026-10-20 10:14
---

## Origin

Spawned from t2063 during Step 8b review.

## Upstream defect

- .aitask-scripts/lib/task_utils.sh:1187,2156 — `task_sync` and `task_data_converge` still gate on `_task_push_has_remote`, which discards a failed `git remote` probe (`2>/dev/null || true`). A repository config git cannot parse therefore reads as `no-remote`, and the sync/converge cycle is skipped silently, with commits pending. This is the same failure class t2063 fixed for `task_push`.

## Diagnostic context

t2063 routed option-prefixed `./ait git push` through `task_push` and carried the user's `-c` / `--config-env` into the push cycle's probes. Review found that with an unreadable config (`-c badkey`, or `--config-env` naming an unset variable) git exits 128 on every command. `_task_push_has_remote` turned that into "no remote", so the push reported `NO_REMOTE`, exited 0 and printed nothing. t2063 fixed `task_push` only: it captures `git remote`'s stdout and status once, and on failure reports FAILED/unknown with git's first line (Test P5 in `tests/test_ait_git_gateway_pull.sh`). `task_sync` (line ~1187) and `task_data_converge` (line ~2156) still call `_task_push_has_remote` and behave the old way. A broken repo-level config there yields `TASK_SYNC_STATUS=no-remote` / `TASK_CONVERGE_STATUS=no-remote` with no warning.

## Suggested fix

Apply the `task_push` pattern from t2063 to both callers: one `git remote` query with its status captured, and a failure reported as `failed` with git's diagnostic rather than `no-remote`. Check what the `ait sync --batch` token vocabulary should print for it. Test with a fixture whose repo config is unparseable, and keep a control showing a genuinely remote-less repo still reports `no-remote` silently.

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-10-20T07:14:55Z status=pass attempt=1 type=human
