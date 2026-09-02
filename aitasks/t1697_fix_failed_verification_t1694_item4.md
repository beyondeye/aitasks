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

### Observed failure (live tmux, 2026-09-02)

`P` hides the parked rows correctly, but when the **currently focused card is the
parked agent being hidden**, focus is stranded and the app stops responding to
**every** keyboard binding — `P`, `Space`, `?`, arrows. The only recovery is a
mouse click on a visible card.

Reproduce from a freshly booted `ait monitor` (verified 3/3 from a cold boot; it
does **not** reproduce once the app has already toggled `P` at least once, so
boot fresh):

1. `Down` — focus the first agent card.
2. `Space`, `Space` — cycle that card to parked (`P`); the row still shows.
3. `P` — the parked row disappears. **Correct so far.**
4. `P` again — nothing happens. `?` does not open the Keys modal. Arrows do
   nothing. `capture-pane -pe` shows **zero** focus highlights, and the preview
   column still renders `This agent is parked — press Space to unpark it.`,
   i.e. `_focused_pane_id` is still the now-hidden parked pane.
5. Click any visible card with the mouse — keys work again and `P` reveals the
   parked row.

With focus on a card that is **not** the one being hidden, the toggle shrinks and
grows the list correctly (11/11 attempts), so the defect is specific to the
focus-handoff path.

### Where to look

`_hand_off_focus_before_hiding` / `_focus_next_visible_card`
(`.aitask-scripts/monitor/monitor_app.py`) are the t1685 code added for exactly
this case. The dead-key symptom is consistent with focus landing on a
`PreviewPanel` (or nowhere) so that `on_descendant_focus` sets
`_active_zone = Zone.PREVIEW`, after which `check_action` disables every binding
except `switch_zone` — and `Tab` cannot be delivered from `tmux send-keys`, so
the user has no keyboard route back. Confirm the zone rather than assuming it.

### Next steps

Reproduce the failure locally (see the commits and files above, and the origin archived plan for implementation context), identify the offending change, and fix. This task was auto-generated from a manual-verification failure in t1694 item #4.
