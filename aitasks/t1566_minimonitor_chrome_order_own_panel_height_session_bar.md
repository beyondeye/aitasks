---
priority: high
risk_code_health: medium
risk_goal_achievement: low
effort: low
depends: []
issue_type: bug
status: Implementing
labels: [minimonitor, tui, layout]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
implemented_with: claudecode/opus5
created_at: 2026-08-18 12:22
updated_at: 2026-08-18 15:53
---

## Symptom

In the 40-column minimonitor companion pane, the top chrome now reads:

```
 multi: 3s · 17a 11 awaiting 1d 4 idle      <- #mini-session-bar
 ⚠ shadow feedback is stale — agent          <- #mini-shadow-stale
 moved on (analyzed 6m52s ago; round 2
 block 2m56s older still)
 ⟳ auto-recheck ARMED                        <- #mini-loop-status
 ── this agent ──                            <- #mini-own-agent (clipped, ▄▄ scrollbar)
 ☆ agent-pick-1563                    ▄▄
   pick confirm dialog same edge
────────────────────────────────────────
 ── aitasks ──
 ...
```

Three problems, all in `.aitask-scripts/monitor/minimonitor_app.py`:

1. **The two live banners sit above the followed agent.** The shadow-stale
   banner and the auto-recheck loop status push the "this agent" panel — the
   pane's primary identity surface — down the screen. They should render
   **below** `#mini-own-agent`, between it and the agent list.

2. **The "this agent" panel is clipped and shows a vertical scrollbar.** It is
   a `VerticalScroll` capped at `max-height: 4`, but its content is
   header (1) + name line (1) + up to 2 wrapped task-title lines + an optional
   phase line, plus a 1-row `border-bottom` — so the panel overflows and paints
   a scrollbar instead of the data. It must be sized so its full content
   always fits with **no vertical scrollbar**.

3. **The top session bar is on by default.** `#mini-session-bar`
   (`multi: 3s · 17a …` / `<session>  N agents`) should be **hidden by
   default**, freeing a row and letting the followed agent sit at the top of
   the pane.

## Origin — this is a t1499 regression

Verified against `8580112e4` ("bug: Undock minimonitor's top chrome so it
renders at all (t1499)"). Before that commit `#mini-own-agent` was
`dock: top; height: auto` with **no cap**, so the panel grew to fit and never
scrolled. t1499 undocked the four top-chrome widgets (Textual gives same-edge
docked siblings the same region, so only the last one composited) and added
`max-height` caps to stop the now-flowing chrome from overrunning the
bottom-docked `#mini-key-hints`. The cap it gave the own-agent panel —
`max-height: 4` — is smaller than the panel's real worst case, which is what
introduced the scrollbar. The banners becoming visible at all is also new with
t1499; their position above the panel was never a deliberate choice.

## Scope

### 1. Chrome order

`compose()` (~line 615) currently yields:

```
#mini-session-bar → #mini-shadow-stale → #mini-loop-status → #mini-own-agent → #mini-pane-list
```

Target order:

```
#mini-session-bar (hidden by default) → #mini-own-agent → #mini-shadow-stale → #mini-loop-status → #mini-pane-list
```

`_TOP_CHROME` (~line 303) lists the same four ids and is consumed by
`_refresh_short_mode`; keep it in sync with compose order (it is order-sensitive
only for readability, but the CSS block comment above the stylesheet describes
the order explicitly and must be updated with it).

### 2. Un-clip `#mini-own-agent`

Size the panel to its real worst case rather than a guessed constant. The
content is built by `_maybe_build_own_agent_panel` → `_own_card_text` /
`_own_agent_identity_text` / `_own_phase_text`:

| row | source | always? |
|---|---|---|
| `── this agent ──` header | `.mini-own-header` | yes |
| `☆ <window name>` | `_own_agent_identity_text` | yes (name may fold above ~36 cols) |
| task title, wrapped | `textwrap.wrap(info.title, …)[:2]` | 0–2 rows |
| advisory phase | `_own_phase_text` | 0–1 rows |
| `border-bottom: solid $primary` | CSS | yes (1 row) |

Acceptance: with a followed agent that has a 2-line wrapped title **and** a
phase line, the panel renders every row and **no scrollbar glyph** appears.
Prefer a derived/`auto` height over a new magic number; if a cap must stay for
the short-mode budget, derive it from the row table above rather than restating
a literal.

### 3. Hide the session bar by default

Decision (confirmed with the user): hide the **bar widget** only —
`monitor.multi_session` stays `True` (default in `TmuxMonitor.__init__`,
`monitor_core.py:1467`) so agents from other sessions/projects keep appearing in
the pane list, and the `M` toggle keeps working.

- `#mini-session-bar` ships hidden (`display: none`), same pattern as the other
  collapsible chrome, so it costs **zero** rows by default (an empty
  `height: auto` Static still occupies one row — see the t1499 stylesheet
  comment).
- `_refresh_session_bar` (~line 1082) must not unhide it unconditionally.
- Provide a way to turn it back on. Config precedent:
  `tmux.minimonitor.width` in `aitasks/metadata/project_config.yaml`, read in
  `main()` (~line 3590) and by `agent_launch_utils.maybe_spawn_minimonitor` —
  a sibling key (e.g. `tmux.minimonitor.session_bar: false` by default) fits
  that shape. Seed the key in `seed/` if the seeded config carries the sibling.

## Interaction with the short-mode budget

`_refresh_short_mode` compacts `#mini-key-hints` to `_SHORT_HINT_ROWS` when the
measured chrome height leaves `#mini-pane-list` less than
`_PANE_LIST_FLOOR_ROWS`. Growing the own-agent panel and dropping the session
bar both change that measurement — re-verify:

- the pane list keeps at least one row at every pane height (the existing
  `test_pane_list_keeps_a_row_at_every_pane_height` case),
- live chrome still never overruns the docked key hints,
- short mode still engages/releases with the banners and stays off for the
  own panel alone.

## Tests

`tests/test_minimonitor_top_chrome_render.py` pins the current geometry and
must be updated in the same change, in particular:

- `test_own_agent_panel_is_visible_and_flows_below_the_banners` — the assertion
  inverts (the panel now flows **above** the banners).
- `CHROME_IDS = list(mm._TOP_CHROME)` and the pairwise ordering assertions in
  `test_top_chrome_widgets_do_not_share_a_region`.
- `test_empty_chrome_costs_no_rows` / `test_collapsible_chrome_returns_to_zero_rows_when_cleared`
  — the session bar joins the collapsible set.
- Add a case that fails on the current build: an own-agent panel with a 2-line
  wrapped title + a phase line renders **all** its rows and shows no scrollbar.

Per the TUI conventions, assert on rendered geometry / composited text (t1499's
own lesson: DOM-level `display` / `visible` / region checks stayed green through
the whole life of that defect) — see
`aidocs/framework/tui_conventions.md`.

## Files

- `.aitask-scripts/monitor/minimonitor_app.py` — `compose()`, the `CSS` block,
  `_TOP_CHROME`, `_refresh_short_mode`, `_refresh_session_bar`, `main()`
- `tests/test_minimonitor_top_chrome_render.py`
- `aitasks/metadata/project_config.yaml` + `seed/` counterpart (if a config key
  is added)
- `.aitask-scripts/lib/agent_launch_utils.py` (only if the spawner needs the new key)

## Out of scope

- t1539 (list scroll position reset) — different widget, in flight.
- t1563 (`TaskPickConfirmDialog` same-edge bottom dock) — different surface, in flight.
- t1481 (validating the configured minimonitor width).
- Changing `multi_session`'s default or the `M` toggle behaviour.

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-08-18T12:54:02Z status=pass attempt=1 type=human
