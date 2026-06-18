---
priority: low
effort: medium
depends: []
issue_type: enhancement
status: Implementing
labels: [brainstorming, tui, ait_brainstorm]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-06-16 08:50
updated_at: 2026-06-18 10:59
boardidx: 40
---

## Origin

Risk-mitigation ("after") follow-up for t983_3, created at Step 8d after
implementation landed.

## Risk addressed

addresses: best-effort graph marks (code-health low)

> **Best-effort graph marks** may leave list and graph views visually
> inconsistent on marked state until a follow-up. · severity: low · →
> mitigation: dag_node_mark_rendering

## Goal

Render the space-marked state (`self._selection.marked`) on `DAGDisplay` nodes
in the Browse graph view, so the graph and list views show selection marks
consistently. t983_3 wired marking into `NodeSelection` and reflected it on the
list-view `NodeRow` glyphs only (the model + list reflection were the hard bar);
the graph-view glyph was deferred here. Add a marked indicator to the DAG node
rendering driven by `self._selection.marked`, refreshed by `_refresh_node_marks`
(extend it to also repaint the DAG), and keep the brainstorm test suite green.
