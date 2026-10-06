---
priority: low
effort: low
depends: []
issue_type: chore
status: Implementing
labels: [shadow, aitask_monitormini, tui, codex]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
anchor: 1892
followup_kind: risk_mitigation
implemented_with: claudecode/opus5_5
created_at: 2026-10-05 23:42
updated_at: 2026-10-06 22:38
---

## Origin

Risk-mitigation ("after") follow-up for t1892, created at Step 8d after implementation landed.

## Risk addressed

only the Codex glyph is measured (goal-achievement)

- Only `•` is measured. opencode and agy were not measured. A different rewrite
  would still not parse, though it would now be *reported*.
  · severity: low · → mitigation: measure_agent_tui_marker_rendering

## Goal

t1892 made the concern parser accept a closed set of **measured** item-marker
glyphs: `_MARKER_GLYPHS = "-•"` in `.aitask-scripts/monitor/concern_parser.py`.
`-` is canonical; `•` is the rewrite measured on codex-cli 0.160.0. The opencode
and agy shadow-pane renderers were not measured.

Measure them live:

1. Run an opencode shadow and an agy shadow in tmux, each bound to a followed
   agent, and have each emit a concern block (a plan review).
2. Capture each pane through the production path
   (`./.aitask-scripts/aitask_shadow_capture.sh --deep --any-pane <pane>`).
3. Inspect the item-marker bytes (`od -c` / `cat -A`) and check that the fences
   and the `Round:` header survive.
4. Run the parser on each capture (`parse_concerns`, `has_concern_block`,
   `unrecovered_markers`).

If a renderer rewrites the marker to a new glyph, add it to `_MARKER_GLYPHS`.
Add it only after this measurement, per the rule in `concern-format.md`
("Accepted marker glyphs"). Add a real-bytes fixture and tests alongside the
Codex ones (`TestCodexBulletMarkers`), and record the fact in
`.claude/skills/aitask-shadow/concern-format.md`. If neither renderer rewrites
it, record that both were measured clean (renderer and version), so the open
question is closed.

Keep the one-glyph-per-block rule and its guards intact (the `_yield_table` /
`_block_glyph` tests in `tests/test_concern_parser.py`).

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-10-06T19:38:37Z status=pass attempt=1 type=human
