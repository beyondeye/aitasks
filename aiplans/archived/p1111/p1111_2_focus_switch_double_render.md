---
Task: t1111_2_focus_switch_double_render.md
Parent Task: aitasks/t1111_monitor_ui_thread_offload_perf.md
Sibling Tasks: aitasks/t1111/t1111_*.md
Worktree: aiwork/t1111_2_focus_switch_double_render
Branch: aitask/t1111_2_focus_switch_double_render
Base branch: main
---

Focus-switch **double-render** + **O(N) card-indicator** fix for the monitor.

## Context
Part of t1111 (`ait monitor` UI-thread offload). On a `PaneCard` focus,
`on_descendant_focus` (`monitor_app.py:1354-1365`) renders the preview **twice** —
directly at line 1359 (`_update_content_preview()`) and again via
`_update_zone_indicators()` (1361 → 1238). Each render is `_ansi_to_rich_text` over
~200 lines. The second is pure waste on a switch (`same_pane` is False).
`_update_selected_card_indicator` (1245-1252) also iterates **all** PaneCards +
`set_class` each. Isolated to `monitor_app.py` (clean file). No threading.

**Scope boundary:** this is the *structural* switch fix. It removes the redundant
second render (~2× win) and the O(N) card scan, but the **single**
`_ansi_to_rich_text` render still runs on the UI thread — so the active-agent
switch lag (ANSI-heavy content) is *reduced ~2×, not eliminated*. Eliminating it is
the sibling **t1111_5** (preview-render offload), which depends on this task.

## Key files to modify
- `.aitask-scripts/monitor/monitor_app.py` only.

## Implementation plan
1. Remove the redundant direct `self._update_content_preview()` at
   `monitor_app.py:1359`; the call via `_update_zone_indicators()` (1361 → 1238)
   covers it → one render on a switch. Confirm `_manage_preview_timer()` (1360) is
   render-independent (it only toggles the 0.3s preview timer by zone). Order stays
   set-zone → manage-timer → update-indicators.
2. Targeted selected-card flip **via a direct mapping, not CSS selectors**:
   - Maintain `self._pane_cards: dict[str, PaneCard]` (pane_id → widget), populated
     in `_rebuild_pane_list` as cards are mounted, cleared/rebuilt each tick.
   - Track `self._selected_card_pane_id`.
   - `_update_selected_card_indicator` unsets the class on `self._pane_cards.get(old)`
     and sets it on `self._pane_cards.get(new)` — no `query("#…")` selector strings,
     so no CSS-escaping / selector-significant-character coupling.
   - Keep a `full=True` pass (iterate the dict's values) for `_restore_focus` (883)
     after a rebuild re-mounts all cards (the `selected` class is lost on remount).
   - The dict is the single source of truth for card lookup.

## Reference patterns
- `_restore_focus` (`monitor_app.py:846-883`) re-applies focus + selected class
  after each rebuild — the `full=True` path must keep working here.
- `PaneCard` (`monitor_app.py:119-124`), CSS `.selected`/`:focus` (346-353).

## Verification
- New `tests/test_monitor_focus_switch.py` using Textual `run_test()` pilot: mount
  `MonitorApp` with ≥2 `PaneCard`s; spy `_update_content_preview`; dispatch a
  `PaneCard` focus → assert called exactly **once** (was twice); assert only the two
  affected cards get `set_class`; render-level assert the `selected` class is on the
  focused card only (per aidocs TUI render-level verification convention).
- Manually: `ait monitor` with all agents idle → arrow focus-switch feels instant.

## Risk
code-health low, goal low. No threading.

## Final Implementation Notes

- **Actual work done:** Removed the redundant direct preview render on `PaneCard` focus so focus switching renders the preview once through `_update_zone_indicators()`. Added a pane-id-to-card mapping and tracked selected pane id so normal selected-card updates touch only the old and new cards, while structural rebuilds still use a full reconciliation pass. Tightened awaiting-input prompt detection to scan only the live bottom of the pane capture, preventing old prompt text in scrollback from marking an active `agent-raw-*` pane as waiting.
- **Deviations from plan:** Included `tests/test_monitor_focus_switch.py` as planned by the verification section, even though the key-file section named only `monitor_app.py`. Also updated `monitor_core.py` and `tests/test_prompt_detection.py` for the false-positive waiting-status regression found during workflow completion.
- **Issues encountered:** A transient false positive for awaiting-input status was reported in `agent-raw-1` during workflow completion. The exact live pane state was not captured before it returned to idle, so prompt matching was hardened against the plausible stale-scrollback cause by using only the bottom prompt window.
- **Key decisions:** `_rebuild_pane_list()` now returns whether it performed a structural rebuild so callers can skip full selected-card reconciliation on the fast update path.
- **Verification:** `python3 -m unittest tests.test_monitor_focus_switch -v` passed 3 tests. `python3 tests/test_prompt_detection.py` passed 7 tests.
