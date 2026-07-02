---
priority: high
effort: low
depends: []
issue_type: bug
status: Implementing
labels: [tmux, monitor, tui, codeagent]
gates: [risk_evaluated]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-07-02 17:06
updated_at: 2026-07-02 17:07
---

Fix code-agent launches from the shared `AgentCommandScreen` so pick/raw/explain/etc. launches do not accidentally reuse an existing TUI window such as `monitor` when the caller passed a new `agent-*` default window name.

## Exploration Summary
- **Observed symptom:** In a live tmux session, launching `/aitask-pick 1111_2` with Codex produced a Codex `node` pane in a tmux window named `monitor` instead of an `agent-pick-1111_2` window.
- **Live evidence:** `tmux list-panes -a` showed Codex/node panes in `aitasks` windows named `monitor`, including one with a companion minimonitor pane.
- **Expected behavior:** Launches initiated by board/monitor/minimonitor/codebrowser with `default_window_name="agent-pick-<id>"` should default to creating that new agent window, so monitor classification, task lookup, and companion minimonitor behavior stay correct.

## Findings
- The monitor launch call sites are passing the correct intended name:
  - `.aitask-scripts/monitor/monitor_app.py` uses `window_name = f"agent-pick-{target_id}"` for sibling pick and restart flows.
  - `.aitask-scripts/monitor/minimonitor_app.py` uses the same `agent-pick-<id>` default for own-window next-sibling launches.
  - Board/codebrowser launch paths also pass `agent-pick-*`, `agent-raw-*`, or `agent-explain-*` names.
- The shared dialog builds the actual `TmuxLaunchConfig` in `.aitask-scripts/lib/agent_command_screen.py`.
- `_compute_window_options()` currently prefers a remembered existing window from `AgentCommandScreen._last_window_by_project` over `_NEW_WINDOW_SENTINEL`.
- `run_tmux()` records existing-window selections globally per project. If a TUI window such as `monitor` was remembered, a later agent launch can default to splitting into that window instead of creating the caller's `agent-*` window.
- Monitor task context depends on the window name contract: `monitor_core.task_id_from_window_name()` only extracts task IDs from `agent-pick-*` / `agent-qa-*` windows, while `monitor` is a TUI window name. Misnamed agent panes lose task association and can break monitor/minimonitor assumptions.

## Suggested implementation
1. Update `AgentCommandScreen` so remembered existing windows do not override the new-window default for agent-launch operations that pass a `default_window_name` with an agent/create prefix.
   - Conservative rule: for operations like `pick`, `raw`, `explain`, `qa`, `resume`, `syncfix`, or any `default_window_name` starting with `agent-`/`create-`, the initial window selection should be `_NEW_WINDOW_SENTINEL` unless the caller explicitly passed `default_tmux_window`.
   - Keep existing split-into-current-window behavior for intentional callers such as codebrowser create-task, where `default_tmux_window` is explicitly provided.
2. Consider adding a helper such as `_should_prefer_new_window()` or an explicit constructor flag if that better matches local style.
3. Ensure `run_tmux()` does not persist TUI window selections in a way that silently poisons later agent launches, or ignore that memory for agent launches.
4. Add focused regression tests around `_compute_window_options()` / `AgentCommandScreen` state:
   - remembered window `9` named `monitor` exists, `default_window_name="agent-pick-1111_2"`, no `default_tmux_window` -> selected value is `_NEW_WINDOW_SENTINEL` and `_build_tmux_config()` uses `agent-pick-1111_2`.
   - explicit `default_tmux_window="9"` remains honored for the create-task/current-window case.
   - normal manual split-memory behavior remains available for non-agent launches if intended.

## Verification
- Run the new/updated `AgentCommandScreen` tests.
- Run relevant existing launch tests, at minimum:
  - `python3 -m unittest tests.test_agent_command_dialog_default_session tests.test_agent_command_dialog_empty_prompt tests.test_agent_command_dialog_narrow -v`
  - any new targeted test module added for the window-selection regression.
- Manual smoke: from `ait monitor` or `ait board`, launch `/aitask-pick 1111_2` with Codex and confirm tmux creates/selects an `agent-pick-1111_2` window, not `monitor`; confirm the pane appears as an AGENT in `ait monitor` with task context.

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-07-02T14:18:48Z status=pass attempt=1 type=human
