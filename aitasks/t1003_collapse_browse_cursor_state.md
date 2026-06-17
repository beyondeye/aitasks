---
priority: medium
effort: medium
depends: []
issue_type: refactor
status: Implementing
labels: [brainstorming, tui, ait_brainstorm]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-06-16 08:50
updated_at: 2026-06-17 22:58
boardidx: 30
---

## Origin

Risk-mitigation ("after") follow-up for t983_3, created at Step 8d after
implementation landed.

## Risk addressed

addresses: dual cursor state (code-health medium)

> **Dual cursor state (`_current_focused_node_id` + `self._selection.primary`)**
> kept in sync by hand creates a temporary implicit contract: a future edit that
> sets one but not the other drifts the selection. Documented debt, to collapse
> in a later child. · severity: medium · → mitigation: collapse_browse_cursor_state

## Goal

Migrate the 13 legacy `_current_focused_node_id` read sites in
`.aitask-scripts/brainstorm/brainstorm_app.py` onto `self._selection.primary`
so there is ONE cursor source of truth, and retire the dual-state debt that
t983_3 introduced. After this lands, `_show_browse_node_detail` should set only
`self._selection.set_primary(node_id)` (no parallel `_current_focused_node_id`
write), and every consumer reads `self._selection.primary` / `.effective()` /
`.cardinality`. Keep the brainstorm test suite green; add/adjust coverage for
the consolidated cursor.
