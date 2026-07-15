---
priority: medium
effort: medium
depends: []
issue_type: feature
status: Ready
labels: [aitask_monitormini, shadow, agent_chooser]
gates: [risk_evaluated]
anchor: 1148
created_at: 2026-07-15 16:47
updated_at: 2026-07-15 16:47
---

## Summary

Follow-up to t1148 (which added the switcher's `X` "explore + pick agent"
shortcut). Apply the same idea to minimonitor's **shadow** launch: add a new
`E` (shift-e) shortcut that launches the shadow companion agent **but first
opens the agent command dialog** (the narrow, minimonitor-width variant of
`AgentCommandScreen`) so the user can confirm / change the code agent and model
before the shadow starts. The existing lowercase `e` fire-and-forget shadow
launch stays unchanged.

## Current behavior

- Binding: `Binding("e", "launch_shadow", "Shadow", show=False)` in
  `minimonitor_app.py` BINDINGS (`.aitask-scripts/monitor/minimonitor_app.py:212`).
- Footer hint lists it in the `#mini-key-hints` Static (`:281-289`):
  the line `"k:kill  n:next  e:shadow\n"`.
- Handler `action_launch_shadow` (`:1064-1165`) is fire-and-forget: it resolves
  `resolve_dry_run_command(target_root, "shadow", followed_pane[, task_id])`,
  builds a specialized `TmuxLaunchConfig`, and calls `launch_in_tmux(...)`
  directly — using the wrapper's default agent/model with no picker.

## Existing pattern to mirror (SAME file — best reference)

Minimonitor **already** opens the narrow `AgentCommandScreen` for its pick flow:
`_launch_pick_for_own` / `action_pick_next_for_own` at
`minimonitor_app.py:1000-1062` constructs
`AgentCommandScreen(..., operation="pick", default_agent_string=agent_string,
narrow=True)` and, in its `on_pick_result` callback, launches via
`launch_in_tmux(screen.full_command, pick_result)`. The `E` shadow handler
should copy this dialog-then-callback shape. (`AgentCommandScreen` and
`resolve_skill_profile` are already imported at `:62`.) The switcher's t1148
`action_shortcut_explore_pick` is the cross-file analogue.

## Key complications (these distinguish this from the simpler t1148 explore case)

The shadow launch is **not** a plain "new window" launch — the new handler must
preserve everything `action_launch_shadow` does today, only inserting the
agent/model picker in front:

1. **Duplicate guard.** `action_launch_shadow` refuses a second shadow per
   followed agent via `_find_shadow_pane_for_sync(followed_pane)` (`:1091-1095`).
   Run this guard **before** opening the dialog (don't pop a picker just to fail).
2. **Specialized placement.** The shadow is placed same-window as a split to the
   RIGHT of the followed AGENT pane, sized to `shadow_pane_width`
   (`split_target_pane=followed_pane`, `split_size=shadow_width`,
   `split_direction`), or a separate `agent-shadow-<task>` window when
   `tmux.shadow_same_window` is false (`:1105-1138`). This placement is richer
   than what the dialog's tmux tab produces by default. **Design decision for
   planning:** reconcile the dialog's returned `TmuxLaunchConfig` with the
   shadow's required placement. The likely-cleanest approach is to use the dialog
   ONLY to let the user change the agent/model (take the agent choice baked into
   `screen.full_command`) and keep building the shadow's own `TmuxLaunchConfig`
   for placement — i.e. do not let the dialog's placement tab override the
   shadow's split geometry. Confirm this against `AgentCommandScreen`'s result
   contract during planning and document the chosen approach.
3. **Post-launch wiring (MUST run in the result callback).** After
   `launch_in_tmux`, `action_launch_shadow` resolves the new pane id from its pid
   (`resolve_pane_id_by_pid`), stamps the authoritative `@aitask_shadow_target`
   option (`SHADOW_TARGET_OPTION`) pointing at the followed pane, and calls
   `attach_shadow_cleanup_hook(followed_pane, companion_pane)` so the shadow dies
   with its agent (`:1145-1165`). Without this the same-window shadow is
   mis-classified as an agent and never auto-killed. This wiring must be
   replicated in the `E` handler's confirm path exactly.
4. **Narrow dialog.** Pass `narrow=True` (minimonitor width), matching the pick
   flow at `:1037`. Minimonitor declares itself narrow via `_switcher_narrow`
   (`:875`); the dialog's narrow layout is the same one used by t1148 on a
   minimonitor host.
5. **operation="shadow".** `shadow` is a valid codeagent operation
   (`aitask_codeagent.sh` SUPPORTED_OPERATIONS). Note it is NOT in
   `agent_command_screen.py:_FRESH_WINDOW_OPERATIONS`, and the shadow's default
   placement is same-window (not a fresh window), so the "+ New window" default
   is intentionally not wanted here — another reason placement should stay
   handler-controlled (see complication 2).

## Proposed change surface (all in `.aitask-scripts/monitor/minimonitor_app.py`)

1. Add `Binding("E", "launch_shadow_pick", "Shadow (pick agent)", show=False)`
   to BINDINGS (`:206-221`), directly after the `e` binding. Shift-`E` is a
   distinct Textual key from `e`. **Check** how minimonitor shortcuts are
   registered/override-resolved (`_shortcuts_scope = "minimonitor"`, `:134`) —
   the `e` binding is a plain literal in BINDINGS, so `E` should be added the
   same way; verify no separate registry step is required for it to bind.
2. Optionally extend the `#mini-key-hints` footer (`:281-289`) to advertise `E`
   (e.g. `e/E:shadow`), keeping the compact width in mind.
3. Add handler `action_launch_shadow_pick` that: runs the duplicate guard and
   resolves `followed_pane`/`task_id`/`target_root` exactly as
   `action_launch_shadow` (`:1077-1099`); resolves
   `resolve_agent_string(target_root, "shadow")` and
   `resolve_dry_run_command(target_root, "shadow", *args)`; opens
   `AgentCommandScreen(..., operation="shadow", operation_args=args,
   default_agent_string=..., narrow=True)`; and in the result callback builds
   the shadow `TmuxLaunchConfig` (same-window split / separate window per config)
   using `screen.full_command`, launches, and runs the full post-launch wiring
   from complication 3. Cancelling the dialog launches nothing.

## Acceptance

- Pressing `E` in minimonitor (with a followed agent present) opens the narrow
  `AgentCommandScreen` for the shadow operation, showing the current default
  agent and letting the user change agent/model.
- Confirming launches a shadow for the followed agent using the chosen
  agent/model, with the SAME placement as the current `e` shortcut (same-window
  split to the right of the agent pane, or separate window per
  `tmux.shadow_same_window`) AND the same `@aitask_shadow_target` stamp +
  cleanup-hook wiring, so the shadow is correctly classified and auto-killed.
- The duplicate-shadow guard still fires (no second shadow per agent), before
  the dialog opens.
- Cancelling the dialog launches nothing.
- The existing lowercase `e` shortcut keeps its fire-and-forget behavior.
- The new shortcut appears in the footer hint (if a hint segment is added).
- Add/extend a test for the new handler (mock `AgentCommandScreen` push +
  result routing, assert operation="shadow" / narrow=True, and assert the
  post-launch stamp + cleanup-hook wiring runs on confirm). Reference test:
  `tests/test_tui_switcher_agent_launch.py` (t1148) and any existing
  minimonitor shadow-launch tests.

## Cross-agent note

This is a Claude Code TUI-source change (minimonitor is Python, not a skill), so
no cross-agent skill port is required.
