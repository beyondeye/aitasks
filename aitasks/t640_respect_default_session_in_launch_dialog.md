---
priority: medium
effort: low
depends: []
issue_type: bug
status: Ready
labels: [tmux, tui]
created_at: 2026-04-24 10:59
updated_at: 2026-04-24 10:59
---

## Context

When the user opens the launch dialog (`AgentCommandScreen`) from `ait board`'s pick (`p`), create (`n`), or brainstorm actions, the **initial tmux session** selected in the session dropdown ignores the project's `tmux.default_session` from `aitasks/metadata/project_config.yaml`.

User-observed symptom: a project configured with `tmux.default_session: aitasks_mob` opens the launch dialog pre-selected on `aitasks` (a sibling project's session that happens to be running), not `aitasks_mob`. Pressing `(R)un in tmux` without noticing lands the code agent in the wrong project's tmux session.

## Root cause

`.aitask-scripts/lib/agent_command_screen.py` `_populate_tmux_tab()` (lines 297-316) picks `initial_session` with this priority:

1. `AgentCommandScreen._last_session` (class-level state, if still in the active sessions list)
2. `sessions[0]` (first entry from `tmux list-sessions`, not project-aware)
3. `_NEW_SESSION_SENTINEL`

`self._tmux_defaults["default_session"]` is loaded (line 218) but is **only** consumed as the placeholder text in the "new session name" input (line 323). It never participates in the initial selection.

## Secondary problem — class-level session memory leaks across projects

`AgentCommandScreen._last_session` and `AgentCommandScreen._last_window` are declared as class attributes (lines 190-191). When the user opens a board in project A, picks session `aitasks`, then later opens a board in project B whose `default_session` is `aitasks_mob`, the dialog in project B still defaults to `aitasks` — violating the "one tmux session per project" invariant documented in `CLAUDE.md`.

## Proposed fix

In `_populate_tmux_tab()`:

1. Change the initial-session priority to:
   - last session remembered **for this project_root** if still in `sessions`
   - else `self._tmux_defaults["default_session"]` if in `sessions`
   - else `sessions[0]`
   - else `_NEW_SESSION_SENTINEL`

2. Apply the same logic to the window selector: prefer last-window for this project, otherwise `_default_tmux_window`, otherwise `_NEW_WINDOW_SENTINEL`.

3. Replace the class-level `_last_session` / `_last_window` with dicts keyed by the resolved absolute `project_root`, so cross-project opens don't bleed:
   ```python
   _last_session_by_project: dict[Path, str] = {}
   _last_window_by_project: dict[Path, str] = {}
   ```

4. Update `run_tmux()` (line 489) to write into the per-project keys on dismiss.

## Files to touch

- `.aitask-scripts/lib/agent_command_screen.py` — the two class attributes, `_populate_tmux_tab`, `run_tmux`.

## Verification

- Manual: with two aitasks projects running side-by-side (each with its own tmux session) and distinct `default_session` values, confirm the launch dialog in each project defaults to that project's `default_session`.
- Manual: pick session in project A's dialog, dismiss, then open project B's dialog — project B should default to its own `default_session`, not A's picked one.
- Unit: `tests/test_agent_command_screen_default_session.sh` — stub `load_tmux_defaults` and `get_tmux_sessions` and assert `initial_session` resolution across the priority cases.

## Non-goals

- Changing `load_tmux_defaults()` itself or the config schema.
- Changing default behavior when `default_session` is not configured (continue to fall back to `sessions[0]`).
