---
priority: medium
effort: low
depends: []
issue_type: bug
status: Implementing
labels: [agent_chooser, aitask_monitormini]
gates: [risk_evaluated]
assigned_to: dario-e@beyond-eye.com
anchor: 1148
created_at: 2026-07-15 17:52
updated_at: 2026-07-15 18:25
---

## Origin

Spawned from t1152 during Step 8b review. The new minimonitor `E`
shadow-launch agent picker surfaced this pre-existing defect (it opens the
shared model picker in narrow mode), but the bug is not caused by t1152.

## Upstream defect

- `.aitask-scripts/lib/agent_model_picker.py:317 — AgentModelPickerScreen is fixed at width:65% and is not narrow-aware; option rows render "<agent>/<name>" and on a narrow minimonitor pane the long "claudecode/" prefix (11 chars) eats the visible width, clipping the claudecode model name (e.g. opus4_8). Shared by board/monitor/codebrowser/switcher, so the fix must stay narrow-aware without regressing the wide hosts.`

## Diagnostic context

- The picker is a second screen pushed by `AgentCommandScreen.action_change_agent`
  (`agent_command_screen.py:759`), constructed as
  `AgentModelPickerScreen(operation, current_agent, current_model, all_models=...)`
  — it is NOT passed the caller's `narrow` flag, so it always uses its own
  `width: 65%` CSS (`agent_model_picker.py:317`).
- Option rows (`FuzzyOption`, `agent_model_picker.py:108-127`) render
  `display_text` (`"<agent>/<name>"`, built in `_build_options_*`,
  e.g. `:489`, `:531`) plus a dim `description`, at `height: 1; width: 100%`
  (`:327`). On a ~40-col minimonitor pane, 65% width minus the ` >> ` prefix and
  the `claudecode/` agent prefix leaves too few columns for the model name.
- `claudecode/` (11 chars) is the longest agent prefix (`codex/`=6,
  `opencode/`=9), so claudecode models clip first / most visibly.

## Suggested fix

Make `AgentModelPickerScreen` narrow-aware: thread a `narrow` flag from
`AgentCommandScreen.action_change_agent` (which already knows `self._narrow`)
and add a `.narrow` CSS variant (wider/full width, and/or shorten the agent
prefix — e.g. show the model name primary with the agent as a dim suffix) so the
model name stays visible on small panes without regressing the board/monitor
wide hosts. Add a render-level test asserting the claudecode model name is
present in the narrow option row.
