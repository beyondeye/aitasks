---
priority: medium
effort: low
depends: []
issue_type: feature
status: Implementing
labels: [tui, switcher, codeagent]
file_references: [.aitask-scripts/lib/tui_switcher.py]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-07-15 10:23
updated_at: 2026-07-15 10:34
---

## Summary

The TUI switcher (`.aitask-scripts/lib/tui_switcher.py`) has an `x` shortcut
that launches an explore agent. It is fire-and-forget: it immediately spawns
`ait codeagent invoke explore` in a new window, using the wrapper's default
code agent / model with no chance to change it.

Add a new `X` (shift-x) shortcut in the switcher that launches the explore
agent **but first opens the existing agent command dialog**
(`AgentCommandScreen`) so the user can confirm / change the code agent and
model before the explore session starts.

## Current behavior

- Binding: `Binding("x", "shortcut_explore", "Explore", show=False)` in
  `_QUICK_JUMP_BINDINGS` (`tui_switcher.py:378`), scope `shared.tui_switcher`.
- Handler `action_shortcut_explore` (`tui_switcher.py:1103-1124`) spawns
  `ait codeagent invoke explore` via `_spawn_in_session` with no dialog and no
  agent/model selection.
- Bottom hint row lists it via `_HINT_ITEMS` (`tui_switcher.py:229`):
  `("shortcut_explore", "explore", "x")`.

## Existing pattern to mirror (same file)

`action_shortcut_agent` — the `e` "Code Agent" shortcut
(`tui_switcher.py:1146-1218`) — already does exactly the dialog-then-launch
flow: it resolves a default command/agent, constructs
`AgentCommandScreen(..., operation="raw", default_agent_string=agent_string,
narrow=self._narrow)`, and on confirm launches via
`launch_in_tmux(screen.full_command, result)`. The dialog's `(A)gent` picker
(`agent_command_screen.py:action_change_agent`) lets the user swap agent/model
and bakes the choice into `screen.full_command`.

The canonical board template is `aitask_board.py:5482-5503` (Pick Task flow):
`resolve_agent_string(Path("."), operation)` -> `AgentCommandScreen(...,
operation=..., default_agent_string=...)` -> `launch_in_tmux(screen.full_command,
result)` in the result callback.

## Proposed change surface (all in `tui_switcher.py`)

1. Add `Binding("X", "shortcut_explore_pick", "Explore (pick agent)",
   show=False)` to `_QUICK_JUMP_BINDINGS` (`:368-382`). Shift-`X` is a distinct
   Textual key from `x`, so there is no collision.
2. Optionally add a hint segment to `_HINT_ITEMS` (`:220-232`), e.g.
   `("shortcut_explore_pick", "explore+", "X")`.
3. Add handler `action_shortcut_explore_pick` that copies the shape of
   `action_shortcut_agent` (`:1146-1218`) but with:
   - `operation="explore"` (already whitelisted in
     `agent_command_screen.py:_FRESH_WINDOW_OPERATIONS`, so the dialog defaults
     to "+ New window"),
   - `default_agent_string = resolve_agent_string(project_root, "explore")`,
   - resolved command via `resolve_dry_run_command(project_root, "explore")`,
   - window base `agent-explore-{n}` with the same uniqueness loop as
     `action_shortcut_explore` (`:1109-1112`),
   - the same stale-selection / `_ensure_session_live` / `_teleport_if_cross`
     / `maybe_spawn_minimonitor` guards used by the existing handlers,
   - `narrow=self._narrow`.

No changes are needed in `keybinding_registry.py`, `agent_command_screen.py`,
or `agent_launch_utils.py` — they already support `operation="explore"` and the
override-aware keybinding registration picks up the new `action_id`
automatically.

## Acceptance

- Pressing `X` in the switcher opens `AgentCommandScreen` pre-populated for the
  explore operation with the current default agent shown and changeable.
- Confirming launches an explore session in a new `agent-explore-N` window
  using the chosen agent/model.
- Cancelling the dialog launches nothing.
- The existing `x` shortcut keeps its current fire-and-forget behavior.
- The new shortcut is override-aware via the shortcuts registry and appears in
  the switcher hint row (if a hint segment is added).
- Add/extend a test alongside `tests/test_tui_switcher_agent_launch.py`.
