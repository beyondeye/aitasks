---
priority: medium
risk_code_health: low
risk_goal_achievement: low
effort: low
depends: []
issue_type: bug
status: Implementing
labels: [tmux, test_infrastructure]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
anchor: 1689
followup_kind: upstream_defect
implemented_with: claudecode/opus5_5
created_at: 2026-10-26 11:36
updated_at: 2026-10-26 12:23
---

## Origin

Spawned from t2142 during Step 8b review.

## Upstream defect

- `.aitask-scripts/lib/pid_anchor.sh:276 — on macOS (no /proc) lock_holder_liveness can only return "unknown" for the weak ps token, so tests/test_lock_anchor_tmux_live.sh, test_live_endpoint_tmux_live.sh, test_note_with_live_composition.sh and test_sync_holder_pane_live.sh fail their alive / LIVE_PANE / live_lock expectations on macOS (24 assertions); previously masked by the socket-path failure`
- `tests/test_tmux_control.sh:22 — PYTHON_BIN defaults to bare python3; a system python without PyYAML fails importing monitor_core (task_yaml) — should default to the framework venv python`

## Diagnostic context

t2142 moved `require_isolated_tmux`'s default `TMUX_TMPDIR` to `/tmp/ait_isolated_tmux_<uid>`, so the six live adopters that run a private `-L ait_<name>_<pid>` server no longer overflow AF_UNIX `sun_path` on macOS (Darwin 24.6). Two of them now pass (test_tmux_pane_for_pid 25/25, test_scratchpad_autosave_live 20/20). The other four get past pane startup and fail later, all on the same verdict:

- test_lock_anchor_tmux_live.sh: 1/11 — "Anchor reads back as alive while the pane is up (expected 'alive', got 'unknown')"
- test_live_endpoint_tmux_live.sh: 11/16 — every case gets `LIVE_NONE:holder_unknown` (expected LIVE_PANE / agent_unknown / no_pane)
- test_note_with_live_composition.sh: 6/117 — `LIVE_NONE:holder_unknown`
- test_sync_holder_pane_live.sh: 6/51 — sub-reason `unknown_liveness` instead of `live_lock`; stderr wording follows from that

Root cause: macOS has no `/proc`, so `get_pid_starttime_kind` returns `ps` (second-granular start time). `lock_holder_liveness` (pid_anchor.sh:253-278) deliberately answers `unknown` for a matching `ps` token, because it cannot rule out same-second PID recycling. Only a `proc` token can be `alive`. So these tests' expectations hold only on Linux. Nothing in this was changed by t2142; the earlier socket failure had hidden it.

Separately, during t2142's regression check, `tests/test_tmux_control.sh` failed with `ModuleNotFoundError: No module named 'yaml'` under `/usr/bin/python3`. It passes with `PYTHON_BIN=~/.aitasks/venv/bin/python`.

## Suggested fix

Decide per test whether a weak token should be accepted on macOS, or whether the test should assert the platform-correct verdict (`unknown` / `holder_unknown` when the kind is `ps`) or skip its alive-dependent cases there. A stronger macOS identity token (e.g. a `sysctl kern.proc` start time with microseconds) is the product-side alternative. For test_tmux_control.sh, default `PYTHON_BIN` to the framework venv interpreter, as the other suites do.

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-10-26T10:23:09Z status=pass attempt=1 type=human

> **✅ gate:review_approved** run=2026-10-26T12:42:59Z status=pass attempt=1 type=human
