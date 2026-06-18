---
priority: low
effort: low
depends: []
issue_type: refactor
status: Ready
labels: [tui_switcher, stats_ui, tui]
anchor: 1025
created_at: 2026-06-18 16:21
updated_at: 2026-06-18 16:21
---

## Origin

Risk-mitigation ("after") follow-up for t1025_2, created at Step 8d after
implementation landed.

## Risk addressed

code-health (residual per-TUI group-cycle widget-wiring duplication; the central
default-resolution is already shared in-task via Step 0).

From t1025_2 plan `## Risk`: "The **central** default-resolution rule is now a
shared, unit-tested pure helper (`default_selected_group`/`advance_selected_group`,
Step 0), so the main drift risk is removed in-task. What remains duplicated is the
per-TUI **widget-wiring** of a group cycle (switcher session-row vs stats sidebar +
title + panes), which is genuinely TUI-specific. · severity: low"

## Goal

If, after t1025_2 landed, the switcher and stats group-cycle action bodies prove
meaningfully duplicative, factor the common sequence — advance group → re-derive
ring → re-point selection when it fell out → refresh — into a shared mixin/helper.
The pure default-resolution (`default_selected_group` / `advance_selected_group`)
already lives in `.aitask-scripts/lib/agent_launch_utils.py`; this task targets
only the residual TUI-side wiring (`_cycle_group` in `tui_switcher.py` and
`stats_app.py`, plus the `_refresh_after_cycle` / `_apply_session_selection`
refresh tails). Keep the TUI-specific widget calls (session row vs sidebar/title/
panes) where they must differ. If the duplication turns out to be minimal, it is
acceptable to close this task as not-worth-the-abstraction.
