---
priority: medium
effort: low
depends: [t461_3]
issue_type: feature
status: Implementing
labels: [brainstorming, agentcrew]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-04-13 11:44
updated_at: 2026-04-14 09:31
---

## Context

Parent task t461 lets users mark code agents for interactive launch.
t461_2 adds the `ait crew setmode` CLI to mutate `launch_mode` on a
Waiting agent. This task wires a small edit flow into the brainstorm
TUI's **status tab** so users can toggle interactive mode on an agent
that has already been created (e.g., it was created headless but the
user now wants to watch it live before it launches).

## Key Files to Modify

- `.aitask-scripts/brainstorm/brainstorm_app.py`:
  - `AgentStatusRow` class (around lines 507-521) — add a keybinding
    binding for `e` (edit mode).
  - `_mount_agent_row()` (around lines 1499-1555) — no change expected,
    but this is where agents are mounted with their current state.
  - `_reset_agent()` (around lines 1459-1472) — use as the closest
    pattern for a row action that mutates an agent's yaml through an
    external helper and refreshes the row.
  - Status tab refresh logic so the row re-renders after an edit.

## Reference Files for Patterns

- `NodeDetailModal` (around lines 164-248) — pattern for a small modal
  with tabs/sections; use as the structural template for the new
  `AgentModeEditModal`.
- `_reset_agent()` (1459-1472) — pattern for "focused row → shell out
  to a script → refresh" which is exactly what this task does with a
  different backing script.

## Implementation Plan

1. **Add a new modal `AgentModeEditModal(ModalScreen)`**:
   - Input: `crew_id: str`, `agent_name: str`, `current_mode: str`,
     `agent_status: str`.
   - Layout: a small panel with two buttons — "Headless" / "Interactive"
     — and a cancel button. Highlight the current mode.
   - If `agent_status` is NOT `Waiting`, render the modal in read-only
     mode: show the current mode, explain that it cannot be changed
     (the setmode CLI would refuse anyway), and offer only a Close
     button.
   - Result value: the selected mode (or `None` on cancel).

2. **Bind `e` key on `AgentStatusRow`**:
   - Add to the row's `BINDINGS = [...]` list (check how `w` for reset
     is bound).
   - Action handler: `action_edit_mode()` that reads the row's current
     agent_name, crew_id, status, and current `launch_mode` (parsing
     the status yaml), then pushes `AgentModeEditModal` on the app.

3. **On modal dismiss**, if a new mode was selected and differs from
   the current value:
   - Shell out to the setmode script asynchronously via Textual's
     worker pattern (mirror `_reset_agent()`):
     ```python
     subprocess.run(["./ait", "crew", "setmode",
                     "--crew", crew_id,
                     "--name", agent_name,
                     "--mode", new_mode],
                    check=False, capture_output=True, text=True)
     ```
   - If exit 0: notify the user via `self.notify("Launch mode
     updated")` and call `_refresh_status_tab()` to re-render.
   - If non-zero: notify with the stderr as an error. Keep the modal
     closed; the user can retry.

4. **Show effective mode inline on the row**: update `AgentStatusRow`'s
   render (or the label format) to include a small badge showing the
   current mode (e.g., `[i]` for interactive, `[h]` for headless, or
   just the word "interactive" when non-default). Keep it subtle so
   the row layout is not disturbed.

5. **Update the status tab footer / help text** to mention the new
   keybinding, matching how other row keybindings are documented.

## Verification Steps

1. Launch `ait brainstorm <task>` with a crew that has at least one
   Waiting agent.
2. Focus the agent row (arrow keys or tab).
3. Press `e`. Confirm the edit modal opens showing the current mode.
4. Switch mode to "Interactive". Confirm:
   - The modal dismisses.
   - A toast notifies "Launch mode updated".
   - The row badge now shows interactive.
   - `cat <crew>/<agent>_status.yaml | grep launch_mode` shows
     `launch_mode: interactive`.
   - A git commit was created by the setmode script.
5. Press `e` again on a Running agent (if you can get one). Confirm
   the modal opens in read-only mode with an explanatory message and
   no mutation occurs.
6. Smoke-test: with the CLI setmode script deleted/moved, press `e`;
   confirm an error toast appears and no crash.

## Dependencies

- Depends on t461_2 for the `ait crew setmode` CLI that this modal
  calls.
