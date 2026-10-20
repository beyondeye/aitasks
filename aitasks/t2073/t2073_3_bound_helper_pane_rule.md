---
priority: medium
effort: high
depends: []
issue_type: refactor
status: Implementing
labels: [aitask_monitormini, tmux, scratchpad]
gates: [risk_evaluated]
assigned_to: dario-e@beyond-eye.com
anchor: 2073
created_at: 2026-10-20 10:31
updated_at: 2026-10-20 15:17
---

## Context

Child of t2073 (minimonitor scratchpad pane). Today the rule "is this pane a helper or
a real agent" is hard-coded for two markers (`@aitask_shadow_target`,
`@aitask_monitor_kind`) and repeated in Python discovery, the frozen-aware window
classifier, the bash companion-cleanup hook and the minimonitor auto-spawn occupancy
check. The scratchpad pane (`@aitask_scratchpad_target=<agent pane>`) must be treated
like a shadow:
- excluded from discovery and snapshots;
- never counted as a real agent;
- killed when its target dies;
- never killed when a sibling dies while its target lives.

This child introduces **one bound-helper rule** that both kinds use. It also fixes the
folded t1388 bug: minimonitor `_find_sibling_pane_id` rung 2 is helper-blind. The
t1388 acceptance criteria are in the parent task's "Merged from t1388" section. Full
design: `aiplans/p2073_minimonitor_scratchpad_pane.md` ("Layering", "One helper rule",
"Discovery").

**Step 0 — coordination gate (before editing `monitor/minimonitor_app.py` only).**
t2065 has uncommitted hunks in that file. Run
`git diff --quiet -- .aitask-scripts/monitor/minimonitor_app.py` and check that t2065's
commit is in `git log`. Do every other step first. If the gate still fails, stop and
ask the user. Do not edit `monitor_app.py`, `monitor_shared.py` or `applink/router.py`.

## Key Files to Modify

- NEW `.aitask-scripts/lib/helper_panes.py` (stdlib only):
  - `SHADOW_TARGET_OPTION` (moved from `monitor_core.py` ~:448);
  - `SCRATCHPAD_TARGET_OPTION = "@aitask_scratchpad_target"`;
  - `SCRATCHPAD_STORE_OPTION = "@aitask_scratchpad_store"`;
  - `BOUND_HELPER_TARGET_OPTIONS = (SHADOW_TARGET_OPTION, SCRATCHPAD_TARGET_OPTION)`;
  - `is_bound_helper(*targets) -> bool`.

  It lives in lib because `monitor_core` already imports `agent_launch_utils`, and
  lib→TUI imports are banned.
- `.aitask-scripts/monitor/monitor_core.py`:
  - import and re-export the new names;
  - `FROZEN_AWARE_PANE_FORMAT` (~:1068): append the scratchpad target,
    `_FROZEN_AWARE_ARITY = 7`;
  - `classify_window_panes` (~:1087): OR the field into `is_helper` inside the
    `not frozen.strip()` clause, leaving the frozen rules unchanged;
  - `_LIST_PANES_FORMAT` (~:2527): append the field at index 15, and add 16 to
    `_LIST_PANES_ARITIES` (~:2549) in the same change;
  - `_parse_list_panes` (~:2562): `continue` on a non-empty `parts[15]` before the
    shadow branch. Never route it into `shadows`, where `commit_snapshots` would make
    it compete with the real shadow.
- `.aitask-scripts/monitor/tmux_monitor.py` — re-exports keep working.
- `.aitask-scripts/lib/agent_launch_utils.py` `_companion_check_and_split` (~:2425-2509):
  add the field before `pane_start_command`, which must stay last; a scratchpad is
  not a real pane.
- `.aitask-scripts/aitask_companion_cleanup.sh`:
  - job 1 (~:67-77): kill panes whose shadow OR scratchpad target equals `$primary`;
  - job 2 (~:79-127): append `|#{@aitask_scratchpad_target}`, read it as the last
    field `scratch`, and skip it with the shadow helper;
  - keep the literal line `if [ -n "$frozen" ]; then`, which `test_cleanup_rule_parity.sh`
    seds.
- `.aitask-scripts/monitor/minimonitor_app.py` `_find_sibling_pane_id` (~:3008-3053)
  rung 2 — **after the Step 0 gate**:
  - list `#{pane_id}\t#{pane_pid}\t<helper targets>\t#{@aitask_monitor_kind}`, with no
    `stdout.strip()`;
  - skip self, bound helpers and companions (`is_live_companion_marker`). Decision:
    companions are filtered, so a second minimonitor is never chosen;
  - the docstring states the t986 guarantee for both rungs.
- aidocs:
  - `aidocs/framework/tmux_gateway.md` option inventory (~:172-206): rows after
    `@aitask_monitor_kind`;
  - `aidocs/framework/tui_conventions.md` companion sections (~:747-924): replace the
    "two-marker shape" with the bound-helper rule and add a "scratchpad is a fourth
    companion-pane case" subsection.

## Reference Files for Patterns

- `tests/test_cleanup_rule_parity.sh`:
  - `build_window` role case (:134-158);
  - `row <name> <expect> <dying> <roles...>` (:284-325);
  - table (:329-357);
  - negative control (:365-399).
- `tests/test_list_panes_arity_characterization.py` (`CURRENT_ARITY = 15` at :65).
- `tests/test_monitor_companion_filter.py` `_line` values dict (:649-672).
- `tests/test_agent_freeze.py` fake pane dicts (:212, :2784-2823).
- `tests/test_multi_agent_window_substrate.sh` (`is_shadow_target` units).

## Implementation Plan

1. `helper_panes.py`, plus the re-exports and imports.
2. `classify_window_panes` format and arity.
3. Discovery format, arity set and exclusion.
4. Occupancy check.
5. Cleanup script jobs 1 and 2.
6. Gate, then rung 2 of `_find_sibling_pane_id`.
7. Tests (below).
8. aidocs.

## Verification Steps

- `bash tests/test_cleanup_rule_parity.sh`:
  - new `scratchpad)` role bound to `$first`;
  - rows: `agent + scratchpad + companion` → window; `agent + agent + scratchpad` →
    pane; a scratchpad bound to the survivor stays;
  - a job-1 kill assertion.
- A tripwire that asserts every option in `BOUND_HELPER_TARGET_OPTIONS` appears in the
  cleanup script's `-F` formats.
- `tests/test_list_panes_arity_characterization.py` with `CURRENT_ARITY = 16` and the
  scratchpad row excluded.
- `test_monitor_companion_filter.py`, `test_agent_freeze.py`,
  `test_multi_agent_window_substrate.sh` (`is_bound_helper` units), an occupancy unit.
- Identity test: `monitor_core.BOUND_HELPER_TARGET_OPTIONS is
  helper_panes.BOUND_HELPER_TARGET_OPTIONS`.
- t1388 test: drive rung 2 directly, with rung 1 forced to `None`:
  - `[minimonitor, shadow, agent]` and `[minimonitor, scratchpad, agent]` → the agent
    id;
  - negative control: the unfiltered fallback fails.
- `bash tests/test_no_lib_to_tui_import.sh`, `bash tests/test_no_raw_tmux.sh`,
  `bash tests/test_companion_cleanup_ordering.sh`, the full Python suite (read the last
  line), `shellcheck .aitask-scripts/aitask_companion_cleanup.sh`.
