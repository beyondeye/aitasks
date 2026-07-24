---
priority: high
risk_code_health: low
risk_goal_achievement: low
effort: low
depends: []
issue_type: bug
status: Done
labels: [aitask_monitor, testing, tmux]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
implemented_with: claudecode/fable5
created_at: 2026-07-24 18:08
updated_at: 2026-07-24 18:20
completed_at: 2026-07-24 18:20
---

## Problem

Agent tmux windows in the `aitasks` session are randomly renamed to `monitor`,
many times a day, and get renamed back to `monitor` even after the user manually
restores the correct window name.

## Root cause (confirmed by live reproduction)

`MonitorApp.on_mount` (`.aitask-scripts/monitor/monitor_app.py:493`) runs
`tmux rename-window -t $TMUX_PANE monitor` whenever the app mounts, guarded only
by `os.environ.get("TMUX")`. Several Python tests mount the **real** `MonitorApp`
via Textual's `app.run_test()`, which fires `on_mount` in-process with no
`TMUX`/`TMUX_PANE` scrubbing and no subprocess stubbing:

- `tests/test_monitor_preview_offload.py`
- `tests/test_monitor_finalize_offload.py`
- `tests/test_monitor_focus_switch.py`
- `tests/test_monitor_refresh_no_sync_tmux.py`
- `tests/test_monitor_shadow_status.py`

When a coding agent runs these tests inside its tmux pane (routine while
developing this framework), the test process inherits the agent's
`TMUX`/`TMUX_PANE`, so the rename targets the **agent's own window** — relabeling
it `monitor` on the live tmux server. Reproduced: running
`python3 tests/test_monitor_preview_offload.py PreviewOffloadTests.test_render_equivalence`
inside a tmux pane renamed the window `agent-explore-1` → `monitor`.

This explains all observed symptoms: it happens only in the `aitasks` session
(only framework-development agents run this suite), many times a day (every
suite run), and recurs after manual renames. The differing aitasks versions in
sibling repos are unrelated — the pinned-rename fix (t941/t1130) is present in
all of them; that fix targets the right pane for a *real* monitor process but
cannot help when test-mounted monitor instances inherit an agent pane's env.

## Suggested fix (structural — make the bad path impossible)

1. Make the mount-time rename opt-in from the real CLI entry point: e.g. a
   `MonitorApp(..., rename_window=True)` constructor flag passed only by the
   production launcher (`__main__` / `aitask_monitor.sh` path), defaulting to
   `False`, so a test-mounted app can never touch the live tmux server. (Note
   `on_mount` also issues a `has-session` probe via the gateway when the session
   name mismatches — consider gating mount-time tmux side effects together.)
2. Additionally scrub `TMUX`/`TMUX_PANE` (and stub/neutralize mount-time tmux
   side effects) in the affected TUI tests — belt-and-braces so future
   mount-time tmux calls also can't leak to the developer's live server.
3. Add a guard test that fails if mounting `MonitorApp` in a test context can
   issue a `rename-window` (negative control: prove the guard fires on the old
   behavior).

## Acceptance criteria

- Running the monitor TUI Python tests inside a live tmux pane never renames
  any window on the tmux server.
- The real `ait monitor` launch path still renames its own window to `monitor`
  (pinned to its own `$TMUX_PANE`), preserving TUI-switcher discovery.
- A guard/regression test pins the no-rename-under-test behavior.

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-07-24T15:13:50Z status=pass attempt=1 type=human

> **✅ gate:review_approved** run=2026-07-24T15:19:47Z status=pass attempt=1 type=human

> **🔄 gate:risk_evaluated** run=2026-07-24T15:20:52Z-risk_evaluated-a1 status=running attempt=1 type=machine
>
> Verifier: `aitask-gate-risk`
> Note: stuckhash:915cba7e421fce7b

> **✅ gate:risk_evaluated** run=2026-07-24T15:20:52Z-risk_evaluated-a1 status=pass attempt=1 type=machine
>
> Verifier: `aitask-gate-risk`
> Result: risk evaluated (## Risk section + both levels present)
> Log: `.aitask-gates/1240/risk_evaluated_2026-07-24T15:20:52Z-risk_evaluated-a1.log`
