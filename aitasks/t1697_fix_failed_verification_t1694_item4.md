---
priority: medium
effort: medium
depends: [1685]
issue_type: bug
status: Ready
labels: [verification, bug]
anchor: 1685
followup_kind: verification_failure
created_at: 2026-09-02 19:02
updated_at: 2026-09-02 19:02
---

## Failed verification item from t1685

> Press `P` in `ait monitor` to hide parked agents, then `P` again to show them; confirm the list shrinks and grows

### Source

- **Manual-verification task:** `aitasks/t1694_manual_verification_park_code_agents_tristate_mark_and_visib.md` (item #4)
- **Origin feature task:** t1685
- **Origin archived plan:** `aiplans/archived/p1685_park_code_agents_tristate_mark_and_visibility_toggle.md`

### Commits that introduced the failing behavior

- 99f6ca2c2 feature: Park code agents with a tristate mark and a visibility toggle (t1685)
- b5317ddeb test: Pin the capture-failure drop in commit_snapshots before adding the parked branch (t1685)

### Files touched by those commits

- .aitask-scripts/aitask_agent_marks.sh
- .aitask-scripts/lib/agent_marks.py
- .aitask-scripts/monitor/minimonitor_app.py
- .aitask-scripts/monitor/monitor_app.py
- .aitask-scripts/monitor/monitor_core.py
- .aitask-scripts/monitor/monitor_shared.py
- tests/data/font_coverage.json
- tests/test_agent_marks_concurrency.sh
- tests/test_agent_marks_liveness.py
- tests/test_agent_marks.py
- tests/test_mark_glyphs_single_source.py
- tests/test_minimonitor_gate_phase_row.py
- tests/test_minimonitor_other_section.py
- tests/test_minimonitor_own_mark.py
- tests/test_minimonitor_scroll_preservation.py
- tests/test_minimonitor_startup_input_latency.py
- tests/test_minimonitor_top_chrome_render.py
- tests/test_monitor_agent_marks_action.py
- tests/test_monitor_agent_marks.py
- tests/test_monitor_modal_space_dispatch.py
- tests/test_monitor_pane_sort_order.py
- tests/test_monitor_parked_capture.py
- tests/test_monitor_parked_filter.py
- tests/test_monitor_session_divider.py
- tests/test_multi_session_minimonitor.sh
- tests/test_multi_session_monitor.sh
- tests/tools/regen_font_coverage.py
- website/content/docs/tuis/minimonitor/how-to.md
- website/content/docs/tuis/monitor/how-to.md
- website/content/docs/tuis/monitor/reference.md

### Next steps

Reproduce the failure locally (see the commits and files above, and the origin archived plan for implementation context), identify the offending change, and fix. This task was auto-generated from a manual-verification failure in t1694 item #4.
