---
priority: medium
effort: high
depends: []
issue_type: feature
status: Ready
labels: [tui, scripts]
children_to_implement: [t713_5, t713_6, t713_7]
created_at: 2026-04-29 08:42
updated_at: 2026-04-30 15:18
boardidx: 50
---

## Goal

Add a new `ait syncer` TUI that tracks remote desync state for the project's
git refs (`main`, `aitask-data`, `aitask-locks`, `aitask-ids`) and provides
an interactive surface for keeping the local worktree(s) in sync with origin.

## Motivation

Surfaced during t712: `aitask_changelog.sh --gather` was silently skipping
tasks whose archive existed on `origin/aitask-data` but had not been pulled
into the local `.aitask-data/` worktree. t712 ships a one-shot warning at
gather start (a `check_data_desync` helper invoked at the top of `gather()`),
but the broader pattern — any TUI / script that reads task data may be looking
at stale state — deserves a dedicated tracker.

The user has explicitly rejected the alternative of extending
`resolve_task_file` / `resolve_plan_file` with a `git show
origin/aitask-data:...` fallback tier (see memory
`feedback_no_workaround_for_root_cause_sync_problems`). The right
framework-level answer is to make desync **visible and resolvable** via a
dedicated tool, not to silently read from remote refs behind the user's back.

## Requirements

1. **TUI conventions.** Follow the existing aitasks TUI structure (board,
   monitor, minimonitor, codebrowser, brainstorm) — Textual-based Python
   under `.aitask-scripts/board/` (or a sibling module), tmux integration,
   single-session-per-project model (see CLAUDE.md "Single tmux session per
   project").
2. **`n` is the create-task key** across every aitasks TUI; pick a different
   letter for the syncer's switcher binding (CLAUDE.md TUI conventions).
3. **Polling.** Periodically `git fetch` (configurable interval, default
   ~30s) for the project's tracked branches and recompute desync.
4. **Display.** List of refs with ahead/behind counts, list of tasks landed
   on remote not yet pulled (with affected file paths), commit messages,
   and basic actions (pull / push).
5. **Settings option.** Add an `aitasks/metadata/project_config.yaml` key
   (e.g., `tmux.syncer.autostart: true|false`) — when `ait ide` starts, the
   syncer TUI launches alongside the other TUIs if enabled.
6. **TUI switcher integration.** Bind a key in
   `.aitask-scripts/lib/tui_switcher.py` (one of the unused letters; not
   `n` which is reserved for create-task) to switch to the syncer. Surface
   a desync count line as info widget content in the switcher modal.
7. **Monitor / minimonitor integration.** Surface the desync count as a
   small line in the existing monitor and minimonitor TUIs (similar to how
   lock warnings or lazygit prompts surface today). One-line summary like
   "aitask-data: 3 commits behind".
8. **Error handling escape hatch.** When `git pull` or `git push` fails
   (merge conflict, non-fast-forward, auth issue), offer to spawn a code
   agent in a sibling tmux pane (modeled on the existing brainstorm /
   explore agent dispatch — and using the companion-pane auto-despawn
   pattern in `.aitask-scripts/aitask_companion_cleanup.sh`) with
   instructions to resolve the git error interactively with the user.
9. **Tests.** Bash test scripts in `tests/` covering the desync calculation
   helpers (the TUI rendering itself follows the existing convention of
   not having Textual snapshot tests).

## Files (anticipated)

- `.aitask-scripts/aitask_syncer.sh` — entrypoint dispatched via `ait`
- `.aitask-scripts/board/aitask_syncer.py` (or sibling module) — Textual
  TUI implementation
- `.aitask-scripts/lib/desync_state.py` (or `.sh`) — pure data helper used
  by syncer + monitor + minimonitor + switcher (extract the
  `check_data_desync` logic from `aitask_changelog.sh:check_data_desync`
  into this shared helper as the second-caller-extraction trigger)
- `.aitask-scripts/lib/tui_switcher.py` — add binding + info widget
- Monitor / minimonitor source files — add desync line
- Settings config layer — add autostart option
- Permission/whitelist touchpoints for `aitask_syncer.sh` per CLAUDE.md
  "Adding a New Helper Script" — 5 touchpoints (Claude / Gemini / OpenCode
  runtime configs + 2 seed mirrors).

## Acceptance

- `ait syncer` opens the TUI and shows live desync state for the project's
  branches.
- Toggling `tmux.syncer.autostart: true` causes `ait ide` to spawn the
  syncer alongside the other TUIs.
- Monitor and minimonitor display a desync summary line.
- TUI switcher shows desync count and provides a binding to jump to syncer.
- `git pull` / `git push` actions work; on failure, the code-agent escape
  hatch launches in a sibling tmux pane.
- All 5 helper-script whitelist touchpoints updated for `aitask_syncer.sh`.
- The `check_data_desync` helper in `aitask_changelog.sh` is replaced by a
  call to the new shared `desync_state` helper (second-caller extraction).

## Notes

- This task is likely complex and may be split into child tasks during its
  own planning (data helper, TUI shell, monitor integration, autostart,
  agent escape hatch).
- See t712 for the original surfacing context and the rejected workaround
  (Option 3 / data-branch fallback in resolver helpers).
