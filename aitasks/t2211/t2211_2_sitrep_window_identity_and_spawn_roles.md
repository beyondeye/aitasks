---
priority: medium
risk_code_health: low
risk_goal_achievement: low
effort: high
depends: [t2211_1, t2037_2]
issue_type: feature
status: Implementing
labels: [sitrep, monitor, tmux]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
anchor: 2175
implemented_with: claudecode/opus5_5
created_at: 2026-11-05 15:35
updated_at: 2026-11-07 22:26
---

## Context

Child 2 of t2211. The `agent-sitrep` window gains a second role pane, the sitrep TUI
(t2211_1, command `ait sitrep tui --root R`). This child teaches the window identity and
spawn machinery about it. One-per-root holds for **both** roles, the four "who is alive"
cases spawn or repair correctly under the existing lock, and the user-confirmed layout is
produced:

```
+----------------+------+
| sitrep agent   | mini |
|                | mon  |
+----------------+      |
| sitrep TUI     |      |
+----------------+------+
```

The TUI sits below the agent, about 40% of the left column; the minimonitor is a
full-height right column. Parent plan:
`aiplans/p2211_sitrep_two_pane_window_with_sitrep_tui.md`.

## Gate and first step

- Depends on **t2037_2** (monitor status client), which has uncommitted hunks in
  `monitor/monitor_core.py` (`seed_pane_cache`) plus a new `monitor/status_client.py`. Do
  not edit `monitor_core.py` until it lands. Then re-read the landed file and confirm `git
  diff HEAD -- <files>` is empty.
- Every new monitor-side consumer must also behave correctly when the app routes through
  `status_client.MonitorClient`.
- t2175_6 (landed `6fc7b3972`) touched `sitrep_close.py` / `sitrep_harvest.py`. Re-read
  them.

## Current machinery (verified during parent planning; re-verify line numbers)

`.aitask-scripts/monitor/monitor_core.py` "Sitrep window" section (~L4939-5163):
- `SITREP_PANE_FORMAT` (~L4953) = `FROZEN_AWARE_PANE_FORMAT` (~L1107, 7 fields) +
  `@aitask_sitrep_root`, `window_name`, `pane_current_path`; `_SITREP_SPLIT=9`.
- `SitrepSpawn(status, pane, window, detail)`. Status is one of `spawned | focused |
  focus_failed | refused`.
- `match_sitrep_pane(out, root, canon, is_helper=None)` (~L4993) skips bad, frozen, dead and
  helper rows. A stamped row for this root wins; otherwise the first unstamped
  `is_sitrep_window` + cwd==root row is the fallback.
- `find_sitrep_pane_status` (~L5039), `_sitrep_spawn_lock` (~L5056, a flock on
  `<socket>.aitask-sitrep-spawn.lock`, 5 s, fail closed).
- `spawn_sitrep(...)` (~L5090) runs canonical_root → lock → lookup → (focus) →
  `spawn_test_pause("spawn:after_lookup")` → `resolve_dry_run_command(root, "sitrep")` →
  `unique_window_name(.., "agent-sitrep")` → `launch_window_pane` →
  `_stamp_or_remove(.., SITREP_ROOT_OPTION, root)` (~L4421). Outside the lock it then runs
  `maybe_spawn_minimonitor(session, window, agent_pane=pane, project_root=root,
  explicit=True, force_companion=True)`.

Helper rule:
- `pane_is_helper(frozen, shadow, monitor_kind, scratch, pid)` (~L1128, frozen-first) is used
  by `classify_window_panes` (~L1147) and `match_sitrep_pane`.
- `classify_window_panes` is consumed by `TmuxMonitor._collapse_window_for` (~L4148),
  `agent_freeze.py` (~L1534 `_other_real_agents`) and `minimonitor_app._find_sibling_pane_id`
  (~L3444).
- Discovery `_parse_list_panes` (~L2870-2980) + `classify_pane` (~L2725) gives an `agent-`
  window AGENT category.
- `lib/helper_panes.py`:
  - `SITREP_ROOT_OPTION` (~L74; explicitly NOT a helper marker);
  - `BOUND_HELPER_TARGET_OPTIONS` (a closed tuple; tripwire in `tests/test_helper_panes.py`;
    parity with `aitask_companion_cleanup.sh` via `tests/test_cleanup_rule_parity.sh`).
- `lib/agent_launch_utils.py`:
  - `maybe_spawn_minimonitor` (~L2745) → `_companion_spawn_lock` → `_companion_check_and_split`
    (~L2679);
  - its gates are `_scan_companion_window` (~L2587): a companion is present by marker or by
    the `ait minimonitor` start command, and `real_panes >= 3` refuses;
  - the split is `split-window -h -P -F #{pane_id} -l <w> [-c root] -t <agent_pane> ait
    minimonitor`, followed by `attach_companion_cleanup_hook`.
- `aitask_companion_cleanup.sh` (pane-died hook):
  - job 1 kills bound helpers;
  - job 2 keeps the companion while a *real* sibling exists, else kills the companion +
    primary (frozen rules a/b).
- `minimonitor_app.MiniMonitorApp._check_auto_close` (~L2086): "alone" = no other pane in the
  window.
- `monitor/sitrep_close.py` (`h` harvest-and-close, `S` open):
  - `is_sitrep_window` skips any pane in `agent-sitrep` (by window name);
  - `kill_agent_run_guarded` is pane-only.

## Required design

### Pre-phase (risk mitigation, from parent plan): `sitrep_tui_consumer_table_characterization`

Before any production edit, write table-driven tests: one row per consumer, fed a pane
stamped `@aitask_sitrep_tui_root=<root>`. Run them and record which rows are red; those are
exactly the rows this child must flip. All rows must be green at the end. The rows:
- discovery/monitor card listing;
- `match_sitrep_pane` fallback;
- minimonitor `_find_sibling_pane_id`;
- `_scan_companion_window`;
- cleanup-script job 2;
- `kill_agent_pane_smart` / `_collapse_window_for` / `count_other_real_agents`;
- `agent_freeze._other_real_agents`;
- `h` gating.

Tests go in `tests/test_sitrep_window.py`, plus a row in `tests/test_cleanup_rule_parity.sh`.

### Two predicates, not one

The TUI pane is:
- **NOT an agent** for listing: monitor cards, the `match_sitrep_pane` fallback, the
  minimonitor's sibling-follow, the `h` harvest target, `kill_agent_run_guarded`
  targets;
- **a REAL occupant** for retention:
  - cleanup job 2 keeps the minimonitor while the TUI lives;
  - smart kill / collapse never collapses the window under the TUI;
  - freeze's other-real-agents.

Write the full consumer table into the plan with the stamp read path per row. Keep
frozen-first everywhere. Adding the stamp to `FROZEN_AWARE_PANE_FORMAT` changes the arity of
every reader, so update all of them, the cleanup script's `-F` formats and the parity test
in the same change.

### Stamp

`TUI_ROOT_OPTION = "@aitask_sitrep_tui_root"` in `lib/helper_panes.py`, set by `spawn_sitrep`
through `_stamp_or_remove`. Add it to the `@aitask_*` option inventory in
`aidocs/framework/tmux_gateway.md`.

### Role lookup

Add `find_sitrep_roles(monitor, root) -> (ok, agent_pane|None, tui_pane|None)`, a single
`list-pane -a` read. A TUI stamped for R in **another** window still counts (never a second
TUI per root). `match_sitrep_pane` keeps its contract for the agent role.

### Four-way spawn under `_sitrep_spawn_lock`

| starting state | action | status |
|---|---|---|
| nothing alive | new window with the agent; `split-window -v -l 40% -t <agent>` running `ait sitrep tui --root R` (a launch helper like `launch_split_pane`, cwd=root); stamp both | `spawned` |
| agent alive, TUI missing | split the TUI under the agent, stamp it | `added_tui` |
| TUI alive, agent missing | `split-window -v -b -t <tui>` with the agent command, stamp it, `attach_companion_cleanup_hook` | `respawned_agent` |
| both alive | as today | `focused` / `focus_failed` |

Keep `spawn_test_pause` seams so the race proofs can pause each path.

### Geometry

`_companion_check_and_split` splits the agent's cell only, so after the TUI split the
minimonitor would sit top-right and the TUI would span the whole bottom.
- Add keyword-only `full_height: bool = False` to `maybe_spawn_minimonitor` →
  `_companion_check_and_split`, adding tmux `-f` to the `-h` split. Only `spawn_sitrep`
  passes it.
- Call it outside the lock on the `spawned`, `added_tui` AND `respawned_agent` paths. The
  "companion present" gate makes it a no-op when the minimonitor survived, and it restores
  the column when it did not.
- Other companion callers keep today's argv; add an argv assertion pinning that.

### Agent exit

The TUI is a real sibling, so the cleanup kills the dead agent pane and keeps the
minimonitor. `_check_auto_close` sees the TUI as company, so it does not close. The TUI shows
"agent not running" (t2211_3). Pin with a test.

### Wire lines

`monitor/sitrep_open.py` + `lib/sitrep_cli.sitrep_open_message`:
- keep `SITREP_SPAWNED:<pane>|<s>:<w>` / `SITREP_FOCUSED:` / `SITREP_FOCUS_FAILED:` /
  `SITREP_REFUSED:` / `SITREP_WARN:`;
- add `SITREP_ADDED_TUI:<pane>|<s>:<w>` and `SITREP_RESPAWNED_AGENT:<pane>|<s>:<w>` (exit
  0);
- the switcher `_open_sitrep_async` and monitor toasts decode them.

### Harvest

`h` must refuse the TUI pane (it is AGENT-category by window name) and keep skipping the
agent. `kill_agent_run_guarded` stays pane-only.

## Tests

- `tests/test_sitrep_window.py`: consumer-table rows, matcher rows with a TUI-stamped pane,
  `find_sitrep_roles`, the four-way spawn table with `FakeMon`, the wire lines.
- `tests/test_cleanup_rule_parity.sh`: a TUI row.
- `tests/test_sitrep_window_live.sh` (isolated tmux, `require_isolated_tmux`; the existing
  harness patches `_COMPANION_ARGV` / `resolve_dry_run_command`; patch the TUI command the
  same way). New scenarios:
  - cold start, agent-only, TUI-only, TUI-only with the companion gone, both alive;
  - **race proofs** extending scenario C's `AITASK_SITREP_SPAWN_PAUSE_FIFO`: concurrent calls
    in each starting state leave exactly one agent and one TUI per root;
  - **coordinates, not counts**: read `#{pane_id} #{pane_left} #{pane_top} #{pane_width}
    #{pane_height} #{window_width} #{window_height}` and assert:
    - agent `left=0, top=0`;
    - TUI `left=0`, `top = agent.top + agent.height + 1`, `width = agent.width`;
    - minimonitor `left = agent.width + 1`, `top=0`, `height = window_height`;
    - agent.height + TUI.height + 1 = window_height.

    A mutant dropping `-f` must turn cold start red.

## Verification

- `bash tests/test_sitrep_window_live.sh`, `bash tests/test_cleanup_rule_parity.sh`,
  `bash tests/test_helper_panes*.sh` (if any), `bash tests/test_kill_agent_run_guarded.sh`.
- `bash tests/run_all_python_tests.sh --test-dir tests` (check the last line verdict).
- `bash tests/test_no_raw_tmux.sh`; `shellcheck` on changed scripts.

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-11-07T20:26:25Z status=pass attempt=1 type=human

> **✅ gate:review_approved** run=2026-11-08T07:02:05Z status=pass attempt=1 type=human
