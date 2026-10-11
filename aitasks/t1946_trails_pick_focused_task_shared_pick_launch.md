---
priority: medium
effort: medium
depends: []
issue_type: feature
status: Implementing
labels: [trails, aitask_board, minimonitor, shortcuts]
gates: [risk_evaluated]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-10-11 16:44
updated_at: 2026-10-11 16:49
---

## Problem

In `ait trails` (the stand-alone By-Trail TUI, `.aitask-scripts/board/trails_app.py`)
there is no way to **pick** the highlighted task: pressing `p` on a focused live
trail member does nothing. The same card in the board's embedded By-Trail view
(`ait board` → `z`) supports `p` → `/aitask-pick <N>` dialog.

## Root cause

Not a regression — a scope decision. The t1794 split (parent plan
`aiplans/archived/p1794_split_board_monofile_and_standalone_trail_tui.md`, "Stand-alone
scope") limited `TrailsApp` to read-only trail flows plus the `/aitask-trail`
launch (`T`). `TrailsApp.BINDINGS` declares no `pick_task` row, and its
`check_action` has no `pick_task` branch.

Pick is an agent launch like `T`: the TUI itself still writes nothing (the
launched skill does, after its own confirmations), so adding it keeps the
"read-only TUI" property true.

## Findings / touchpoints

### Pick plumbing lives in the board, which trails cannot import (C1)

`trails_app.py` must never import `aitask_board` (contract C1, `board/__init__.py`).
Board-side pick code:
- `KanbanApp.action_pick_task` — `.aitask-scripts/board/aitask_board.py:~4720`
  (focused card → `_focus_existing_agent_window(num)` → `_resolve_pick_command` →
  `AgentCommandScreen` → `on_pick_result`: "run" → `run_dialog_command(...)`,
  `TmuxLaunchConfig` → `launch_in_tmux` + `maybe_spawn_minimonitor`; fallback
  `run_aitask_pick` when the dry-run resolve fails).
- The detail-screen "pick" result path — `aitask_board.py:~4558` (same dialog).
- `_resolve_pick_command` / `_resolve_pick_profile` — `aitask_board.py:~5217`.
- `_focus_existing_agent_window` — `aitask_board.py:~5235` — uses `_current_tmux_session()`
  (`:1173`) and a **raw `tmux select-window` subprocess**; `aitask_board.py` is in the
  `tests/test_no_raw_tmux.sh` allowlist, but a moved copy must go through the
  `lib/tmux_exec.py` gateway (see `aidocs/framework/tmux_gateway.md`).
- `run_aitask_pick` — `aitask_board.py:~5367` (no-dry-run fallback).

`board_trail_screen.TrailScreenMixin` already hosts the shared
`run_dialog_command` (every AgentCommandScreen "run" branch, incl. the board's
pick) and the host hook `_after_dialog_command(refocus_filename)`, which in
`TrailsApp` reloads trail tasks and re-renders — so the post-run refresh already
exists on the trails side.

### Pick-dialog construction is duplicated across TUIs — consolidate in lib

`lib/agent_launch_utils.pick_launch_argv(project_root, task_id)` (t1705_5) is the
shared "resolve pick command + `agent-pick-<id>` window name" helper. It is used
by `monitor/minimonitor_app.py` (`_launch_pick`, ~:3184), `monitor/monitor_app.py`
twice (`_launch_pick_for_sibling` ~:3712, `_on_restart_confirmed` ~:3800) and
`lib/agent_restore.py` — but **not by the board**, which still calls its own
`_resolve_pick_command` (same `resolve_dry_run_command(root, "pick", num)`).

The `AgentCommandScreen("Pick Task t<N>", full_cmd, "/aitask-pick <N>",
default_window_name=…, project_root=…, operation="pick", operation_args=[N],
default_agent_string=resolve_agent_string(root, "pick"), skill_name="pick",
default_profile=resolve_skill_profile("pick", root)[, narrow=True])`
construction is repeated at **5 sites**: board `action_pick_task`, board
detail-pick path, monitor_app ×2, minimonitor `_launch_pick` (`narrow=True`).

Add a single lib builder next to `pick_launch_argv` (e.g. in
`agent_command_screen.py` or `agent_launch_utils.py`, wherever avoids an import
cycle) that returns the configured screen (or None when the command cannot be
resolved), and route all sites — plus the new trails site — through it.

**Keep per-caller result policy local** (memory: "dedupe keeps each caller's
labels"): the board supports the "run in terminal" branch via
`run_dialog_command`; the monitors only handle `TmuxLaunchConfig`; minimonitor
kills the outgoing pane only AFTER a successful launch (load-bearing — it shares
the followed agent's window); monitor restart kills first; notify wording differs
per caller ("Launch failed: …", "Launched agent for t<N>", "Restarted agent …",
board's silent refresh). Pin each caller's existing labels/notify strings against
pre-refactor behaviour. `pick_launch_argv`'s `agent_string=None` default contract
(`tests/test_pick_launch_argv.py`) must be preserved.

The "focus an existing `agent-pick-<N>` / `agent-resume-<N>` window instead of
launching a duplicate" check should move to shared code too (gateway-based), so
both board and trails get it.

### Binding: one shared object (C10)

`TrailsApp` registers under shortcut scope `"board"` and declares the **same**
Binding objects as the board so a `shortcuts.board.<action>` override rebinds
both surfaces (see `TRAIL_BINDINGS` in `board_trail_screen.py`). The board's
`Binding("p", "pick_task", "Pick")` is currently inline in `KanbanApp.BINDINGS`
(`aitask_board.py:~2301`). Hoist it to a shared constant (importable without
`aitask_board`) and declare that same object in both apps.

Pinned by `tests/test_trails_app.py:~541-580` (TrailsApp rows that are board
actions must match the board's `(key, description)`; binding-set / scope tests),
`tests/test_shortcut_scopes.py`, `tests/test_shortcuts_registry_coverage.sh`
(trails_app registers under board scope), and `TrailsApp._shortcuts_exclude_sources`.

### Trails host policy

- Target = the focused **live local member** only — same rule as `T`
  (`TrailsApp._trail_task_target`, `trails_app.py:~380`): `TrailTaskCard` with
  `not is_ghost`, own id via `topic_semantics.task_own_id`. Ghost (archived /
  cross-repo / deleted) cards and no-focus → hidden in footer via `check_action`
  AND a visible refusal inside the action (a remapped key or the command palette
  can still reach it), silent while a modal is up.
- After a "run" launch: `_after_dialog_command` reload already covers it; after a
  tmux launch, re-render (status change is picked up by `r`).

### Docs

- `website/content/docs/tuis/trails/reference.md` — key table (add `p`, next to the `T` row).
- `website/content/docs/tuis/trails/_index.md` — the "read-only … the two keys that
  start trail authoring" paragraph must mention pick as another agent launch.
- `website/content/docs/tuis/trails/how-to.md` if it walks the card keys.
- Run `python3 check_links.py --build` (in `website/`) after editing.

## Acceptance

- `p` on a focused live local member in `ait trails` opens the same
  `/aitask-pick <N>` dialog the board does (or focuses the existing agent
  window); ghost / unfocused → hidden in footer + warning, no launch.
- Board By-Trail and Kanban `p` unchanged; monitor / minimonitor pick paths
  unchanged in behaviour and wording.
- One shared `p` Binding object across board and trails; a
  `shortcuts.board.pick_task` override rebinds both.
- No new raw-`tmux` call site (`bash tests/test_no_raw_tmux.sh` passes); C1 holds
  (`trails_app.py` / shared modules don't import `aitask_board`).
- Tests: trails pick launch / ghost refusal / binding identity; dedupe regression
  pinning each caller's dialog args and notify strings; existing
  `tests/test_board_dialog_run_dispatch.py`, `tests/test_trails_app.py`,
  `tests/test_trail_screen_host_protocol.py`, `tests/test_minimonitor_pick_by_number.py`,
  `tests/test_pick_launch_argv.py` stay green.
