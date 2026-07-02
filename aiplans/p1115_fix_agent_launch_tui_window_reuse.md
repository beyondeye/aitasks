---
Task: t1115_fix_agent_launch_tui_window_reuse.md
Worktree: aiwork/t1115_fix_agent_launch_tui_window_reuse
Branch: aitask/t1115_fix_agent_launch_tui_window_reuse
Base branch: main
---

# Plan - t1115: Fix Agent Launch TUI Window Reuse

## Context

Task t1115 fixes a desktop TUI launch bug: `AgentCommandScreen` can default a
code-agent launch into a remembered existing tmux window such as `monitor`
instead of creating the caller-provided `agent-*` window. Live tmux state showed
Codex `node` panes running in `monitor` windows, while monitor/minimonitor
callers pass `default_window_name="agent-pick-<id>"`.

The core contract is that code-agent panes used by the monitor live in windows
whose names carry task context, especially `agent-pick-<id>` and `agent-qa-<id>`.
`monitor_core.task_id_from_window_name()` only extracts task IDs from those
names; `monitor` is a TUI name.

## Files

- `.aitask-scripts/lib/agent_command_screen.py`
  - Add a small policy helper for when a launch should default to a fresh
    caller-provided window.
  - Use that policy in `_compute_window_options()` so per-project remembered
    existing-window state cannot override agent/create launch defaults.
  - Keep explicit `default_tmux_window` behavior intact for intentional
    split-current-window callers.
- `tests/test_agent_command_dialog_default_session.py`
  - Add pure unit coverage for the new window-selection policy and
    `_compute_window_options()` behavior.

## Implementation Steps

1. Inspect `AgentCommandScreen._compute_window_options()`.
   - It currently builds options with `+ New window` first, then existing windows.
   - It chooses in this order:
     1. explicit `self._default_tmux_window`
     2. `AgentCommandScreen._last_window_by_project`
     3. `_NEW_WINDOW_SENTINEL`
   - That second branch is the bug for agent launches.

2. Add a helper near `pick_initial_session()` or as a private method on
   `AgentCommandScreen`.
   - Preferred shape:
     ```python
     def should_default_to_new_window(
         default_window_name: str,
         operation: str | None,
         explicit_tmux_window: str | None,
     ) -> bool:
         ...
     ```
   - Return `False` when `explicit_tmux_window` is set; explicit caller intent
     must keep winning.
   - Return `True` for `default_window_name` prefixes that represent framework
     code-agent or companion windows:
     - `agent-`
     - `create-`
   - Optionally include operation names as a belt-and-suspenders signal:
     `pick`, `raw`, `explain`, `qa`, `resume`, `syncfix`.
   - Keep the helper pure so tests do not need Textual runtime setup.

3. Update `_compute_window_options()`.
   - Continue honoring `self._default_tmux_window` first when it is live.
   - If the new helper says to default to a fresh launch window, set
     `value = _NEW_WINDOW_SENTINEL` before considering
     `_last_window_by_project`.
   - Otherwise preserve the existing remembered-window behavior.
   - This keeps intentional split flows available for non-agent launches and
     for callers that pass `default_tmux_window`.

4. Confirm `_build_tmux_config()` needs no structural changes.
   - When the window selector value is `_NEW_WINDOW_SENTINEL`, it already reads
     `#tmux_new_window_input`, whose value is `self.default_window_name`.
   - The expected result for `/aitask-pick 1111_2` is:
     `TmuxLaunchConfig(window="agent-pick-1111_2", new_window=True)`.

5. Add regression tests.
   - In `tests/test_agent_command_dialog_default_session.py`, import:
     `AgentCommandScreen`, `_NEW_WINDOW_SENTINEL`, and the new helper if it is
     module-level.
   - Use `unittest.mock.patch` to patch
     `agent_command_screen.get_tmux_windows`.
   - Clear and restore `AgentCommandScreen._last_window_by_project` around each
     test so tests do not leak class-level memory.
   - Test cases:
     1. remembered window index `9` named `monitor`, screen configured with
        `default_window_name="agent-pick-1111_2"`, operation `pick`, no
        `default_tmux_window` -> `_compute_window_options("aitasks")` returns
        `_NEW_WINDOW_SENTINEL`.
     2. same windows and remembered value, but screen configured with
        `default_tmux_window="9"` -> returns `"9"`.
     3. non-agent/default launch such as `default_window_name="scratch"`,
        operation `None`, remembered value `9` -> existing behavior remains and
        returns `"9"`.

6. Run focused tests:
   ```bash
   python3 -m unittest tests.test_agent_command_dialog_default_session -v
   python3 -m unittest tests.test_agent_command_dialog_empty_prompt tests.test_agent_command_dialog_narrow -v
   ```

7. Optional manual smoke after code lands:
   - From `ait monitor` or `ait board`, launch `/aitask-pick 1111_2` with Codex.
   - Confirm tmux creates/selects `agent-pick-1111_2`, not `monitor`.
   - Confirm `ait monitor` classifies the pane as an agent and shows task context.

8. Step 9 post-implementation:
   - Run the declared gate orchestrator (`./ait gates run 1115`).
   - Archive `t1115` only after declared gates pass.

## Risk

### Code-health risk: medium
- `AgentCommandScreen` is shared by board, monitor, minimonitor, codebrowser,
  syncer, and raw-agent launch paths; an over-broad defaulting rule could remove
  an intentional split-into-existing-window workflow. Keep explicit
  `default_tmux_window` precedence and add tests for preserved non-agent memory
  behavior. · severity: medium · -> mitigation: covered_in_task_tests

### Goal-achievement risk: low
- The suspected failure path is localized and matches the live symptom:
  remembered existing-window state can select `monitor` despite an `agent-pick-*`
  default. The fix directly targets that selection policy. · severity: low ·
  -> mitigation: covered_in_task_tests

No separate risk-mitigation tasks are planned; the mitigation is included in this
task's required regression tests.
