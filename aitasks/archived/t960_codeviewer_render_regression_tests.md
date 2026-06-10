---
priority: medium
risk_code_health: low
risk_goal_achievement: low
effort: medium
depends: []
issue_type: test
status: Done
labels: [ait_brainstorm]
assigned_to: dario-e@beyond-eye.com
implemented_with: claudecode/opus4_8
created_at: 2026-06-10 10:36
updated_at: 2026-06-10 11:15
completed_at: 2026-06-10 11:15
---

## Origin

Risk-mitigation ("after") follow-up for t959, created at Step 8d after implementation landed.

## Risk addressed

Addresses code-health risk (medium) from the t959 risk evaluation:
- `CodeViewer` is load-bearing and PyPy-routed; moving its render loop into the shared `NumberedSourceView` base and unifying `_highlighted_lines`→`_lines` touched the core render path.
- The annotation-gutter precompute moved from inline-in-`_rebuild_display` to a `_prepare_build` hook + per-row `_extra_cell` lookup; an off-by-one in the `file_idx - _build_start` index would mis-render the gutter.

## Goal

Add a render-level regression test for codebrowser's `CodeViewer`. The t959 refactor onto `NumberedSourceView` is covered today only by `tests/test_code_viewer_control_chars.py`, which does not exercise the render loop. Use a Textual pilot harness (mirror `tests/test_brainstorm_proposal_preview.py`) to assert:

- one Rich `Table` row per source line; `_total_lines == len(splitlines())`.
- 3-column layout (line number + content + annotation gutter); per-line highlight spans present.
- annotation gutter: `set_annotations(...)` populates the correct rows — verify `_extra_cell` indexing off `_build_start`, including in viewport mode.
- cursor/selection row styles (`CURSOR_STYLE` / `SELECTION_STYLE`) applied to the right rows after `move_cursor` / `extend_selection`.
- wrap-vs-truncate toggle (`cycle_wrap_mode`): truncation appends `…` past `min(MAX_LINE_WIDTH, code_width)`; wrap mode does not.
- viewport windowing for >2000-line files: "N lines above/below" indicator rows appear and `row_count == viewport_size + indicators`.

## Key files
- `.aitask-scripts/codebrowser/code_viewer.py` (`CodeViewer`)
- `.aitask-scripts/lib/numbered_source_view.py` (shared base)
- NEW: `tests/test_code_viewer_render.py`
- Reference harness: `tests/test_brainstorm_proposal_preview.py`; see plan `aiplans/archived/p959_*` Final Implementation Notes for the smoke-test shape already validated manually.
