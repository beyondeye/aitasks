---
priority: medium
risk_code_health: low
risk_goal_achievement: low
effort: low
depends: []
issue_type: bug
status: Done
labels: [minimonitor, tui, tmux]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
anchor: 2227
followup_kind: upstream_defect
implemented_with: claudecode/opus5_5
created_at: 2026-11-07 23:07
updated_at: 2026-11-08 09:52
completed_at: 2026-11-08 09:52
---

## Origin

Spawned from t2227 during Step 8b review.

## Upstream defect

- `.aitask-scripts/lib/tui_switcher.py:1532` — passes a listing-time
  `target.window_index` into `agent_launch_utils` companion spawning and
  `select-window` (`agent_launch_utils.py:2537`, `:2695-2874`). This is the
  same stale-index class t2227 fixed in the minimonitor and `monitor_core`,
  but in the switcher/launcher subsystem. A `renumber-windows` shift between
  the switcher's listing and the action (a window closing meanwhile) can spawn
  the companion into, or select, the NEIGHBOURING window.
- `tests/test_board_movement.py:1291` —
  `IsolationNegativeControlTests.test_in_process_task_dir_override_reads_the_real_repo`
  asserts against the live repo's active task list. It fails at pure HEAD
  whenever an unexpected task file such as `t2226_*` is present, so it is not
  hermetic. This defect is unrelated to the first; it surfaced in the same
  full-suite triage.

## Diagnostic context

t2227 (commit 434b9d306): the minimonitor resolved its followed agent by
`window_index`. Starting a pick from a window while killing that origin window
let `renumber-windows` move the new window onto the origin's index, and a
pre-kill snapshot then matched the origin agent. The fix there:
- identify panes by pane id (`%N`), which never changes;
- use tmux's documented resolution of a pane id given as a WINDOW target
  (`-t %N` means "the window this pane is in now");
- refuse an action unless its listing contains the expected pane.

A probe on a scratch `tmux -L` socket confirmed that `list-panes -t %N` and
`select-window -t %N` both resolve to the pane's post-renumber window
(`kill-window -t %N` was already used in production).

Checked and left as-is in t2227: `monitor_app.py` (index used for display and
sort only), shadow pairing (keyed on the `@aitask_shadow_target` pane id) and
`status_protocol` (index for display and sort only).

The rest of `agent_launch_utils` (`:616`, `:2048-2078`, `:2468-2479`) also
handles `window_index`. Audit each site: an index read and used within one
call is a short race; an index carried over from an earlier listing (the
switcher's `item.window_index` / `target.window_index`) is the t2227 class.

## Suggested fix

Carry a stable identity from the switcher listing instead of the index:
- prefer the window id (`@N`) or the agent pane id;
- target `-t @N` / `-t %N` in the `maybe_spawn_minimonitor` and
  `select-window` paths;
- verify, where an action depends on it, that the target window still holds
  the expected pane.

For the test: make the board-movement isolation control use a fixture task
dir, not the live repo.

## Inbox
<!-- Appended by the note framework. Do not edit by hand; use `./ait note`. -->

> **✉ note:t2233** id=2026-11-08T08:30:52Z.5c3c9e319ebf0b69b8fda680 from=t2233 from_verified=yes at=2026-11-08T08:30:52Z base=97af1d19ae282df63a283693757f25a30b657244 base_branch=main dirty=yes host=omg16
>
> | t2233 (fixture coupling follow-up from t2211_2) relies on your plan's step 5 for its first defect: the hermetic rewrite of tests/test_board_movement.py IsolationNegativeControlTests (two temp roots + sentinels, no live aitasks/ read). As observed when this note was written, that edit is UNCOMMITTED in the shared working tree; t2233 does not touch the file and will not commit it for you.
> | 
> | Consequences for you (advisory):
> | - t2233's archival is blocked until your commit tagged (t2230) carries that control; t2233 then verifies the committed blob (and HEAD) and re-runs IsolationNegativeControlTests against `git show HEAD:tests/test_board_movement.py`.
> | - If you drop, revert or rescope that edit, t2233's first defect (the control fails whenever a real task file ends in `_fixture.md`, e.g. t2226 today) comes back — please note t2233 in that case.
> | 
> | t2233's own change is tests/test_sitrep_window.py only (pid-scoped `_is_companion_process` neutraliser for LIVE_PID fixtures); no overlap with your files.

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-11-08T06:56:03Z status=pass attempt=1 type=human

> **✅ gate:review_approved** run=2026-11-08T07:42:06Z status=pass attempt=1 type=human

> **🔄 gate:risk_evaluated** run=2026-11-08T07:52:07Z-risk_evaluated-a1 status=running attempt=1 type=machine
>
> Verifier: `aitask-gate-risk`
> Note: stuckhash:14012cb06ffc7dce

> **✅ gate:risk_evaluated** run=2026-11-08T07:52:07Z-risk_evaluated-a1 status=pass attempt=1 type=machine
>
> Verifier: `aitask-gate-risk`
> Result: risk evaluated (## Risk section + both levels present)
> Log: `.aitask-gates/2230/risk_evaluated_2026-11-08T07:52:07Z-risk_evaluated-a1.log`
