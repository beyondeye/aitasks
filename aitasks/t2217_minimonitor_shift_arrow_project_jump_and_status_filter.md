---
priority: medium
effort: medium
depends: []
issue_type: feature
status: Ready
labels: [minimonitor, monitor, keybindings, tui]
gates: [risk_evaluated]
created_at: 2026-11-05 14:43
updated_at: 2026-11-05 14:43
---

## Goal

Add two shift+arrow key pairs to `ait minimonitor`, show the active filter in the
top chrome, and document both in the in-app key-help screen (`H`) and the website
how-to.

1. **shift+↑ / shift+↓ — jump to the previous / next project.** Scroll the agent
   list so the first card of the previous / next project group sits at the top of
   the list (and focus that card).
2. **shift+← / shift+→ — cycle a status/phase filter.** The list then shows only
   the code agents in the selected status or gate phase.
3. **Filter indicator** in the top minimonitor chrome, carrying the key that
   changes it.
4. **Help** — both features documented in the minimonitor help modal (and key band).

## Behaviour (decided during exploration)

### shift+↑ / shift+↓ (project jump)
- A "project" is a session group in the list — the groups `_build_list_entries`
  delimits with `format_session_divider` (one tmux session per project). Groups
  only exist in multi-session mode (`M`); with a single group there is nothing to
  jump to.
- It is a **scroll**: when the whole agent list already fits on screen the keys
  do nothing (no max_scroll_y ⇒ no-op). Decide during planning whether focus still
  moves to the target group's first card in that case — the user's statement is
  that "they obviously do nothing" when everything fits, so default to a true no-op.
- **Wraps**: shift+↓ on the last group goes to the first group; shift+↑ on the
  first goes to the last.
- The "current group" is the one containing the focused card (or, if none is
  focused, the group at the top of the viewport).
- Must cooperate with `MiniPaneList`'s scroll seams (t1539 restore anchor, t1653
  bottom pin): a user-driven jump has to retire any pending restore rather than be
  overwritten by it, and must not be classified as an uninvited scroll. Read the
  `MiniPaneList` docstring (`minimonitor_app.py` ~line 748) before choosing the
  scroll call.
- The OTHER section is grouped by session too (`append_group` is shared) — decide
  whether its groups are jump targets (recommend: agent section only, or both in
  list order — pick one and test it).

### shift+← / shift+→ (filter)
- Cycle, **wrapping both ways**: `all → PLAN → IMPLEMENT → POSTIMPL → parked →
  frozen → all` (shift+← walks it backwards; ← from `all` goes to `frozen`).
- Phases come from `lib/workflow_phase.py` (`PHASES = PLAN, IMPLEMENT, POSTIMPL,
  UNKNOWN`) via `MiniMonitorApp._phase_for_snap`. The phase is ADVISORY — filtering
  the visible list is a display use, never gating (aidocs/framework/shadow_agent.md).
  Agents whose phase is UNKNOWN or that have no task are excluded from the phase
  filters (decide during planning whether an explicit `unknown` stop is worth adding).
- Parked and frozen are **marks/states, not phases**: parked/frozen rows never
  compute a phase (not captured). Phase filters therefore show only live,
  non-parked agents; the `parked` / `frozen` filters show only those rows.
- Interaction with the existing `P` filter (`_hide_inactive`,
  `monitor_shared.action_toggle_parked_visibility`): selecting `parked` / `frozen`
  must show those rows even when `P` is hiding them (the explicit filter wins).
  Keep the `P` action id unchanged (it is a persisted override key — see that
  docstring).
- Under any filter other than `all`, hide the OTHER section (no phase/status).
- In-memory per instance, like `_hide_inactive` (no persistence — a forgotten
  filter must not hide agents across restarts).
- Compute each agent's phase ONCE per tick and reuse it for both filtering and the
  card's gate/phase row (`_agent_card_text` currently calls `_phase_for_snap`
  itself) — don't double the per-tick cost.
- The docked followed agent (`#mini-own-agent`) is never in the list and is not
  affected by the filter.
- A notify toast on change (like `P`) is fine, but the indicator below is the
  durable signal.

### Filter indicator
- A new one-row `#mini-filter-status` Static in the top chrome, reading e.g.
  `filter: IMPLEMENT  ⇧←/→` — **shown only while a filter other than `all` is
  active** (0 rows otherwise, like `#mini-loop-status`). It shows the ACTIVE keys
  from the App's composed `BINDINGS` (a user rebind must reach it — use
  `minimonitor_keys.key_display` / `binding_keymap`, never
  `keybinding_registry.resolve_key`).
- Add it to `_TOP_CHROME` (compose order) and to the `_MAX_CHROME_ROWS`
  derivation; re-check `test_pane_list_keeps_a_row_under_full_live_chrome` and the
  short-mode logic (`_refresh_short_mode`).
- Optionally mirror the filter as a compact term on the session bar when that bar
  is enabled (`tmux.minimonitor.session_bar`).
- Consider whether the `P` filter state should also surface in this row (it
  currently has no persistent indicator at all) — at minimum don't contradict it.

## Touchpoints

- `.aitask-scripts/monitor/minimonitor_app.py` — `BINDINGS` (~1354), `on_key` /
  `_nav` (~3349), `_build_list_entries` (~3199), `_agent_card_text`, `compose`,
  `_TOP_CHROME` / `_OWN_PANEL_MAX_ROWS` / `_MAX_CHROME_ROWS` (~1048), CSS.
- `.aitask-scripts/monitor/minimonitor_keys.py` — `FULL_HINT_LINES` and `KEY_HELP`:
  **every binding must appear in both** (parity test-pinned in
  `tests/test_minimonitor_key_hints_modes.py`). The band's row budget is tight:
  rendered height at (15, 30) must stay ≤ 29 and exactly 10 rows at width 40 —
  MEASURE, don't eyeball (see the comment block above `FULL_HINT_LINES`). A single
  segment such as `⇧↑↓:project ⇧←→:filter` may be needed; `HintSeg` supports
  multiple actions joined by `/`.
- `.aitask-scripts/lib/keybinding_registry.py` — new actions get registered through
  the App's BINDINGS (check `tests/test_shortcut_overrides_survive.py`).
- `website/content/docs/tuis/minimonitor/how-to.md` — new how-to sections + Key
  Bindings Quick Reference rows. `KEY_HELP` entries are condensed from this page
  (code_conventions.md), so add the source comments. Run `website/check_links.py
  --build` after editing.
- Possibly `website/content/docs/tuis/minimonitor/_index.md` if it lists keys.

## Notes

- No tmux conflict: the user's tmux.conf binds only `M-S-` / `C-M-S-` arrows.
  Shift+arrows arrive in Textual as `shift+up` etc.; plain up/down are handled in
  `on_key` and must stay unaffected.
- Full-monitor (`ait monitor`) parity is out of scope; mention it as a possible
  follow-up.
- Tests: filter cycling + wrap (both directions), `P` interaction, OTHER hidden
  under a filter, indicator visible only when filtering and showing rebound keys,
  project jump + wrap in multi-session mode, no-op when the list fits, chrome-row
  and key-band budget tests updated.
