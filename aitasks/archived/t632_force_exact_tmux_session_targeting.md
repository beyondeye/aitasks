---
priority: high
effort: medium
depends: []
issue_type: bug
status: Done
labels: [tmux]
assigned_to: dario-e@beyond-eye.com
implemented_with: claudecode/opus4_7_1m
created_at: 2026-04-23 17:12
updated_at: 2026-04-23 18:08
completed_at: 2026-04-23 18:08
---

## Symptom

When running multiple aitasks projects side-by-side with distinct tmux session names configured in each project's `aitasks/metadata/project_config.yaml` (e.g., `aitasks` and `aitasks_mob`), running `ait ide` from one project silently attaches to the wrong project's tmux session. TUIs, singleton windows (monitor, lazygit), and brainstorm sessions from different projects cross-contaminate — whichever project spawned a TUI first "wins" the session for subsequent operations.

Observed example: `ait ide` opens the `aitasks_mob` tmux session even though `tmux.default_session: aitasks` is configured correctly. The settings TUI (which reads `project_config.yaml` directly) correctly reports the configured name, confirming the config is fine — the bug is in how tmux targets are resolved.

## Root Causes

### 1. tmux `-t <name>` is prefix-match by default

`tmux` resolves `-t <name>` as a prefix match against session names unless the target is written as `-t =<name>` (exact match). The session name `aitasks` is a prefix of `aitasks_mob`, so when only `aitasks_mob` is running:

```
$ tmux has-session -t aitasks     # rc=0 — wrongly succeeds
$ tmux list-windows -t aitasks    # returns aitasks_mob's windows
$ tmux attach -t aitasks          # attaches to aitasks_mob
```

Every downstream `-t aitasks:monitor`, `-t aitasks:`, `select-window -t aitasks`, etc. therefore targets the wrong session.

### 2. `find_window_by_name` scans all sessions

`.aitask-scripts/lib/agent_launch_utils.py:152-161`:

```python
def find_window_by_name(name: str) -> tuple[str, str] | None:
    for session in get_tmux_sessions():
        for idx, win_name in get_tmux_windows(session):
            if win_name == name:
                return (session, idx)
    return None
```

This iterates *all* running tmux sessions and returns the first match — cross-project by design. Used by `aitask_board.py:3877` (brainstorm launch), so an `aitasks` project can redirect a brainstorm switch into `aitasks_mob`'s window.

**Design invariant** (confirmed with user): the aitasks framework is designed to run exactly one tmux session per project. Cross-session lookups are always a bug, even when prefix-match is also fixed.

## Fix Approach

### Part A — Force exact match at every `-t <session>` site

Prefix the session name with `=` wherever it is used as a tmux target that should resolve to a session. Approximately **~59 call sites** (49 Python + 10 shell). Known offenders:

**Shell:**
- `.aitask-scripts/aitask_ide.sh:87,93,94,95,97` — `select-window`, `has-session`, `list-windows`, `new-window`, `attach` — the direct cause of the reported `ait ide` symptom.

**Python — `.aitask-scripts/lib/agent_launch_utils.py`:**
- Line 137 — `get_tmux_windows`: `list-windows -t <session>`
- Line 183 — `switch-client -t <session>`
- Line 187 — `new-window -t <session>:`
- Line 219 — `_lookup_window_name`: `list-windows -t <session>`
- Line 310 — `maybe_spawn_minimonitor` window lookup: `list-windows -t <session>`
- Line 329 — `list-panes -t <session>:<idx>`
- Line 349 — `split-window -t <session>:<idx>`
- Line 357 — `select-pane -t <session>:<idx>.0`
- Line 381 — `set-environment -t <session>`
- Line 392 — `list-windows -t <session>`
- Line 413 — `new-window -t <session>:`

**Python — other files:**
- `.aitask-scripts/monitor/monitor_app.py:538` — `has-session -t <expected_session>`
- `.aitask-scripts/monitor/monitor_app.py` ~1627 — tmux_config read (no change, config-only)
- `.aitask-scripts/monitor/minimonitor_app.py:543,557` — `list-windows`, `select-window`
- `.aitask-scripts/agentcrew/agentcrew_runner.py:472,480` — `get_tmux_windows`, pane targeting
- `.aitask-scripts/lib/agent_command_screen.py:371` — `get_tmux_windows`
- `.aitask-scripts/lib/tui_switcher.py:260,406,421,436,447` — TUI switcher `new-window`/`select-window`/`list-windows`
- `.aitask-scripts/board/aitask_board.py:3881` — brainstorm select-window

When the target is `<session>:<window>` or `<session>:<idx>`, the `=` goes only on the session part: `=<session>:<window>`.

Best approach: add a small helper (e.g., `tmux_target(session)` returning `f"={session}"` or `tmux_target(session, window)` returning `f"={session}:{window}"`) in `agent_launch_utils.py` and replace the current inline f-strings. In shell, either change every site in `aitask_ide.sh` and any other scripts, or introduce a `SESSION_T="=${SESSION}"` variable.

Do a full grep sweep to make sure no `-t` targeting a session or session:window pair is missed:

```bash
grep -rn '"-t",' .aitask-scripts/ --include="*.py"
grep -rn 'tmux .*-t' .aitask-scripts/ --include="*.sh"
```

### Part B — Scope `find_window_by_name` to the current project session

Change `find_window_by_name(name)` to accept an explicit `session: str` parameter (or take it from `load_tmux_defaults(Path.cwd())` / the current tmux session via `_detect_current_session()`) and iterate only that session's windows. Update the single caller (`aitask_board.py:3877`) to pass the correct session.

Optionally: consider whether `get_tmux_sessions()` has any other callers that cross project boundaries (e.g., agent_command_screen session picker) and whether those should also be scoped.

## Tests / Manual Verification

Manual verification (requires two aitasks projects side by side with session names that share a prefix — e.g., `aitasks` and `aitasks_mob`):

1. `tmux kill-server` to clear all sessions.
2. `cd /home/ddt/Work/aitasks_mobile && ait ide` — confirm it starts the `aitasks_mob` session with a `monitor` window.
3. Detach (`Ctrl-b d`).
4. `cd /home/ddt/Work/aitasks && ait ide` — **must** start a new `aitasks` session, not attach to `aitasks_mob`.
5. `tmux list-sessions` should show both `aitasks` and `aitasks_mob`.
6. Switch TUIs in each project (board, codebrowser, settings) and confirm each project's windows stay in its own session — no cross-leakage.
7. Start a brainstorm in project A, verify project B doesn't inadvertently focus A's brainstorm window.

Add at least one automated shell test under `tests/` that exercises the prefix-match case by creating two dummy tmux sessions with shared prefix and asserting that a helper (or `aitask_ide.sh` via a dry-run mode if available) correctly targets the exact one.
