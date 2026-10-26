---
priority: medium
effort: low
depends: []
issue_type: test
status: Ready
labels: [tmux, test_infrastructure]
gates: [risk_evaluated]
anchor: 1689
followup_kind: risk_mitigation
created_at: 2026-10-26 16:35
updated_at: 2026-10-26 16:35
---

## Origin

Risk-mitigation ("after") follow-up for t2152, created at Step 8d after implementation landed.

## Risk addressed

shared refactor unverified on Linux (no CI job, no local Linux runtime)

> The shared refactor (`get_pid_identity`, the writer `read -r` split, the liveness strength `case`) executes on Linux, but no checked-in CI job runs the lock/crash-recovery/merge-lock shell suites and the implementing host has no Linux runtime; in-session evidence is limited to the stub-driven proc-branch cases in Test 19. · severity: medium

## Goal

t2152 changed shared code in `.aitask-scripts/lib/pid_anchor.sh`, `aitask_lock.sh` and `lib/merge_lock.sh`:
- the new single-probe `get_pid_identity`, with `get_pid_starttime` / `get_pid_starttime_kind` turned into wrappers;
- the `read -r kind token` writer split;
- `lock_holder_liveness`'s new strength `case`.

All of it executes on Linux, but it was only verified on macOS.

On a Linux host, run each file individually and record its summary line (expected: zero failures):

- `bash tests/test_crash_recovery_pid_anchor.sh`. Test 19's non-Darwin branch must run: `bsdinfo` is not a source off macOS, and a `bsdinfo` lock reads `unknown`.
- `bash tests/test_lock_live_holder_gate.sh`
- `bash tests/test_task_lock.sh`
- `bash tests/test_lock_diag.sh`
- `bash tests/test_lock_anchor_tmux_live.sh`
- `bash tests/test_live_endpoint_tmux_live.sh`
- `bash tests/test_note_with_live_composition.sh`
- `bash tests/test_sync_holder_pane_live.sh`
- `bash tests/test_sync_protect_paths.sh`
- `bash tests/test_sync_deferral_and_quarantine.sh`
- `bash tests/test_merge_lock_broker.sh`
- `bash tests/test_merge_lock_concurrency.sh` (this suite's Case 2 is known to fail on macOS for a pre-existing reason, tracked in t2156. Report the Linux result either way)
- `bash tests/test_merge_broker_rendered_verdicts.sh`
- `bash tests/test_session_hook.sh`

Any failure that is caused by t2152 is a bug to fix (or a follow-up to file); pre-existing failures should be confirmed against the commit before t2152 (`eb8c2b272^`).
