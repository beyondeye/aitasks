---
Task: t777_17_per_run_profile_edit_in_agentcommandscreen.md
Parent Task: aitasks/t777_modular_pick_skill.md
Sibling Tasks: aitasks/t777/t777_*_*.md
Parent Plan: aiplans/p777_modular_pick_skill.md
Base branch: main
---

# Plan: t777_17 — Per-run profile (E)dit in `AgentCommandScreen`

## Scope

Add the "Profile" row + `(E)dit` button + sub-modal (reusing `ProfileEditScreen` from t777_16) to `AgentCommandScreen`. Saved edits write a one-shot override YAML; the dialog's launch command reactives flip to `ait skillrun --profile-override <path>`.

## Step Order

1. Extend `AgentCommandScreen.__init__` with `skill_name`, `default_profile`.
2. Add Profile row to `compose()` (above existing Agent row at ~line 251).
3. Add `e` keybinding + `action_edit_profile` method that pushes `ProfileEditScreen`.
4. `on_save` callback writes override YAML to `/tmp/ait-run-override-<pid>.yaml`.
5. Update `_refresh_command()` (or reactive watchers) to construct the override-aware launch command.
6. Update callers in `aitask_board.py` (`AgentCommandScreen(...)` at lines 3891, 3994, 4035, 4176) to pass `skill_name` and `default_profile`.
7. Confirm `aitask_skillrun.sh` (t777_5) accepts `--profile-override` and deletes the override file after consuming.

## Critical Files

- `.aitask-scripts/lib/agent_command_screen.py` (modify)
- `.aitask-scripts/board/aitask_board.py` (modify caller invocations)
- `.aitask-scripts/aitask_skillrun.sh` (verify `--profile-override` from t777_5)

## Pitfalls

- **Reactive command construction** — Textual reactives may fire mid-mount; ensure the override flag toggles cleanly.
- **Override-file lifecycle** — written by the TUI, deleted by the wrapper after render. If the wrapper crashes, the file may persist; consider a TMP cleanup heuristic.
- **PID-based filename** — use `os.getpid()` of the TUI process, not of the launched agent.

## Verification

See task description Verification Steps. Manual end-to-end through `ait board` is the gold-standard test.
