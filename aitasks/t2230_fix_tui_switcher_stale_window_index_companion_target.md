---
priority: medium
effort: low
depends: []
issue_type: bug
status: Implementing
labels: [minimonitor, tui, tmux]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
anchor: 2227
followup_kind: upstream_defect
created_at: 2026-11-07 23:07
updated_at: 2026-11-07 23:44
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
