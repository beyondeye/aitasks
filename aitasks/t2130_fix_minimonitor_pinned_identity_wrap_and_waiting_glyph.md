---
priority: medium
effort: low
depends: []
issue_type: bug
status: Ready
labels: [minimonitor, gates, ui]
gates: [risk_evaluated]
anchor: 2128
followup_kind: upstream_defect
created_at: 2026-10-23 00:17
updated_at: 2026-10-23 00:17
---

## Origin

Spawned from t2128 during Step 8b review.

## Upstream defect

- `.aitask-scripts/monitor/minimonitor_app.py:2727 — pinned own-agent identity: at width 22 with a long (pathological) window name, the mark glyph "☆" wraps onto a row of its own (identity = 3 rows, not the 2 _OWN_PANEL_MAX_ROWS budgets at :1039), so the panel cap hides the phase row entirely; measured identical with the pre-t2128 unstyled phase`
- `.aitask-scripts/lib/workflow_phase.py:674 — the waiting glyph "⏸" U+23F8 is emoji-capable and covered by neither supported Nerd Font (t1685's recorded rejection in tests/tools/regen_font_coverage.py), yet ships in every phase rendering`

(Line numbers as of commit 12ca11785.)

## Diagnostic context

t2128 added a per-phase glyph and colour to the minimonitor phase row and budgeted the docked own-agent card's phase row (`_own_phase_budget`, `format_phase_markup`). Its composited regression `OwnPanelSizingTests.test_the_longest_phase_stays_on_one_row_at_every_width` (tests/test_minimonitor_top_chrome_render.py) runs every width 40/30/26/22 with the short window name, but the 120-char `OWN_WINDOW_PATHOLOGICAL` name only at 40/30/26. At 22 with that name the composited panel reads:

```
 ── this agent ──
 ☆
 agent-xxxxxxxxxxxx
 xxxxxxxxxxxxxxxxx…
   chrome order own
   panel height
────────────────────
```

The mark glyph sits on its own row, so the identity block costs 3 rows; `_OWN_PANEL_MAX_ROWS` (identity = 2 rows, "mark glyph inline on line 1") is violated and the 7-row cap drops the phase row whatever it contains. Probed identical with the pre-t2128 `[dim]<phase>[/]` rendering, so this is not a phase-width problem: `_own_agent_identity_text` wraps the name to `wrap_width = max(8, target_width - 4)`, and the `☆ ` prefix composed in `_own_card_text` does not fit beside the first wrapped line at 22. `test_own_panel_holds_its_cap_at_every_pane_width` only asserts height <= cap and no scrollbar, so it cannot see the lost row.

Separately, the `⏸` waiting glyph appended by `workflow_phase._phase_body` is exactly the codepoint t1685 rejected for the parked mark (emoji-capable, uncovered by both fonts in `mark_glyphs.SUPPORTED_FONTS`); it renders on every phase row in both monitors.

## Suggested fix

1. Identity: wrap the first name line to `wrap_width - <mark glyph cells>` when a mark glyph is present (or budget the panel for the fold), then extend the t2128 regression to `OWN_WINDOW_PATHOLOGICAL` at width 22 and assert the phase row is visible.
2. Waiting glyph: pick a measured replacement under the `mark_glyphs` policy (covered by every supported font, not emoji-capable, 1 cell), record it in `EXTRA_MEASURED_CODEPOINTS`, and update the phase tables in the minimonitor/monitor docs.
