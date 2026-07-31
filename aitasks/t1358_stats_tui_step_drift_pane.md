---
priority: medium
effort: medium
depends: []
issue_type: feature
status: Ready
labels: [reporting, tui]
gates: [risk_evaluated]
anchor: 1357
created_at: 2026-07-31 10:59
updated_at: 2026-07-31 10:59
---

## Context

Deferred follow-up of t1357 (per-step execution stats for task-workflow),
created at decomposition time as an explicit follow-up task (user decision:
defer the TUI surface, but track it as a concrete task, not a vague
deferral). Blocked on the whole t1357 family landing (`depends: [1357]`).

t1357_4 delivers step-timing + WoW/MoM drift as text sections in `ait stats`
(loader: `.aitask-scripts/lib/stats_step_data.py` — the ONE validated reader
for `aitasks/metadata/stats/events/<YYYY-MM>/*.jsonl`). This task adds the
visual surface: a stats-TUI pane charting step medians over time.

Note: t1357_7 (retrospective) re-prioritizes this task against real usage —
check its findings before implementing.

## Scope

- New pane under `.aitask-scripts/stats/panes/` (model: `pipeline.py`,
  `velocity.py` — plotext charts inside the Textual stats TUI,
  `stats/stats_app.py`).
- Chart: per-step median duration over weeks/months (line per step, or a
  selectable step with per-dimension breakdown: agent, model, effort).
- Drift flags from `stats_step_data.py` rendered as annotations/highlights.
- Reuse the loader — do NOT re-parse event files in the pane.
- Pane registration + keybinding per `aidocs/framework/tui_conventions.md`
  (read before editing any Textual TUI).
- Website docs: stats TUI page under `website/content/docs/` if the stats
  TUI is documented there (check; workflows _index.md is a manual list).

## Verification

- Render-level tests per `feedback_tui_render_level_verification`: assert
  pane content via widget.render() on fixture data; narrow-width behavior
  checked (visible is not readable — budget the surface).
- Python suite runner green (read only the last verdict line).
