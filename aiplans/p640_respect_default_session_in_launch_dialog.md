---
Task: t640_respect_default_session_in_launch_dialog.md
Worktree: (none — working on current branch)
Branch: main
Base branch: main
---

## Context

When the user opens the launch dialog (`AgentCommandScreen`) in a project with `tmux.default_session: aitasks_mob` configured, the dialog pre-selects `aitasks` (a sibling project's running session) instead of `aitasks_mob`. Pressing "(R)un in tmux" without noticing lands the code agent in the wrong project's tmux session — a silent cross-project leak that violates the "one tmux session per project" invariant documented in `CLAUDE.md` memory.

Two cooperating bugs produce this:
1. `_populate_tmux_tab()` ignores `self._tmux_defaults["default_session"]` when picking the initial session — the value is only consumed as the placeholder of the "new session name" input.
2. `AgentCommandScreen._last_session` / `_last_window` are **class-level** attributes, so a selection made in project A's dialog persists across to project B's dialog, shadowing whatever B has configured.

## Files to modify

- `.aitask-scripts/lib/agent_command_screen.py` — sole edit target. Changes are localized to the two class attributes, `_populate_tmux_tab()`, and `run_tmux()`.

## Changes

### 1. Replace class-level last-session/window with per-project dicts

**Current (lines 189-191):**
```python
# Class-level state remembered across dialog opens
_last_session: str | None = None
_last_window: str | None = None
```

**Replace with:**
```python
# Per-project remembered selections, keyed by resolved project_root.
# Class-level (process lifetime) but partitioned per project to prevent
# cross-project leakage documented in CLAUDE.md ("one tmux session per project").
_last_session_by_project: dict[Path, str] = {}
_last_window_by_project: dict[Path, str | None] = {}
```

### 2. Resolve project_root once in `__init__` for stable dict keys

In `__init__` (line 212), after the existing `self._project_root = project_root or Path.cwd()`, add:
```python
self._project_key = self._project_root.resolve()
```
`Path(".").resolve()` returns the absolute CWD at dialog-open time, which gives a stable key. Callers always pass `Path(".")` from the board/codebrowser/monitor, so resolving inside `__init__` is the single right place.

### 3. Use `default_session` from config in initial selection

**Current (`_populate_tmux_tab()`, lines 305-311):**
```python
# Determine initial session selection
if AgentCommandScreen._last_session and AgentCommandScreen._last_session in sessions:
    initial_session = AgentCommandScreen._last_session
elif sessions:
    initial_session = sessions[0]
else:
    initial_session = _NEW_SESSION_SENTINEL
```

**Replace with:**
```python
# Determine initial session selection. Priority:
# 1. Last session chosen in THIS project (per-project memory).
# 2. project_config.yaml's tmux.default_session, if live.
# 3. First live session (fallback for legacy/unconfigured projects).
# 4. _NEW_SESSION_SENTINEL when no sessions exist.
last_for_project = AgentCommandScreen._last_session_by_project.get(self._project_key)
default_from_config = self._tmux_defaults.get("default_session")
if last_for_project and last_for_project in sessions:
    initial_session = last_for_project
elif default_from_config and default_from_config in sessions:
    initial_session = default_from_config
elif sessions:
    initial_session = sessions[0]
else:
    initial_session = _NEW_SESSION_SENTINEL
```

### 4. Use per-project last-window in window selection

`_update_window_options()` currently (line 382) only consults `self._default_tmux_window`. Extend the preference order for existing-window selection:

**Current (lines 383-391):**
```python
if self._default_tmux_window:
    matching = [idx for idx, _name in windows
                if idx == self._default_tmux_window]
    if matching:
        win_select.value = matching[0]
    else:
        win_select.value = _NEW_WINDOW_SENTINEL
else:
    win_select.value = _NEW_WINDOW_SENTINEL
```

**Replace with:**
```python
last_window_for_project = AgentCommandScreen._last_window_by_project.get(self._project_key)
live_indices = {idx for idx, _name in windows}
if self._default_tmux_window and self._default_tmux_window in live_indices:
    # Caller-supplied explicit window takes priority (split-pane flow).
    win_select.value = self._default_tmux_window
elif last_window_for_project and last_window_for_project in live_indices:
    win_select.value = last_window_for_project
else:
    win_select.value = _NEW_WINDOW_SENTINEL
```

The caller's `default_tmux_window` stays the top signal (used by monitor/board split-pane launches to "spawn next to me"). Per-project last-window is the next best guess. `_NEW_WINDOW_SENTINEL` remains the fallback.

### 5. Persist per-project selections in `run_tmux()`

**Current (lines 489-500):**
```python
@on(Button.Pressed, "#btn_run_tmux")
def run_tmux(self) -> None:
    config = self._build_tmux_config()
    if config:
        self._store_command()
        # Remember selections for next dialog open
        AgentCommandScreen._last_session = config.session
        if config.new_window:
            AgentCommandScreen._last_window = None
        else:
            AgentCommandScreen._last_window = f"{config.window}"
        self.dismiss(config)
```

**Replace with:**
```python
@on(Button.Pressed, "#btn_run_tmux")
def run_tmux(self) -> None:
    config = self._build_tmux_config()
    if config:
        self._store_command()
        # Remember selections for next dialog open in THIS project only.
        AgentCommandScreen._last_session_by_project[self._project_key] = config.session
        if config.new_window:
            AgentCommandScreen._last_window_by_project.pop(self._project_key, None)
        else:
            AgentCommandScreen._last_window_by_project[self._project_key] = f"{config.window}"
        self.dismiss(config)
```

### 6. Keep `_NEW_SESSION_SENTINEL` handling unchanged

The existing branch at `_populate_tmux_tab()` that calls `self._show_new_session_input()` when `initial_session == _NEW_SESSION_SENTINEL` still works — no changes there.

The "new session name" input placeholder keeps using `self._tmux_defaults["default_session"]` (line 323) — this is unrelated to the initial-selection fix and is correct behavior.

## Non-goals

- No change to `load_tmux_defaults()` or config schema.
- No change to the "prefer_tmux" auto-tab-switch logic (line 289).
- No migration/persistence of the per-project dicts to disk — they reset every time the TUI restarts. That's the same behavior as today for the class-level attrs; persistence across TUI restarts is a separate feature, out of scope.
- No change to callers (board, codebrowser, monitor) — all already pass `project_root=Path(".")`, so the `__init__` resolve() covers them uniformly.

## Verification

### Manual (primary verification for this TUI change)

1. **Config respected on first open:** In a project configured with `tmux.default_session: aitasks_mob`, with both `aitasks_mob` and `aitasks` tmux sessions running, open `ait board`, press `p` on a task. Dialog's session dropdown must default to `aitasks_mob`.
2. **No cross-project leak:** Open `ait board` in project A (default_session `aitasks`), press `p`, pick `aitasks`, dismiss. Switch to project B (default_session `aitasks_mob`), open `ait board`, press `p`. Dialog must default to `aitasks_mob`, NOT `aitasks`.
3. **Per-project memory within same project:** In project B, open dialog, switch session to `aitasks_other`, confirm. Close dialog, reopen in same project B. Dialog must default to `aitasks_other` (last-used for this project wins over config default).
4. **Fallback when config session not live:** Kill `aitasks_mob` tmux session. In project B (config still says `aitasks_mob`), open dialog. It must fall back to a live session (first in list), not crash.
5. **Window per-project memory:** Launch a task in session A, window `agent-pick-42`. Close dialog. Reopen in same project. Window dropdown should default to the remembered window (when that window is still alive and caller did not pass `default_tmux_window`).

### Unit (targeted)

Add `tests/test_agent_command_screen_default_session.sh`:
- Import `AgentCommandScreen` in a minimal textual App harness (pattern: see any existing `tests/test_*_board.py` if applicable — otherwise a light Python-only test using pytest-style assertion on the resolved `initial_session`).
- Monkeypatch `get_tmux_sessions` → `["aitasks", "aitasks_mob"]` and `load_tmux_defaults` → `{"default_session": "aitasks_mob", ...}`.
- Assert:
  - Fresh dict → `initial_session == "aitasks_mob"` (config wins).
  - Prime dict with `{project_root: "aitasks"}` → `initial_session == "aitasks"` (per-project memory wins).
  - Prime dict for DIFFERENT project_root → `initial_session == "aitasks_mob"` (no cross-project leak).
  - Empty sessions list → `initial_session == _NEW_SESSION_SENTINEL`.
  - `default_session` not in sessions → falls back to `sessions[0]`.

If textual harness is too heavy for a shell test, test the selection logic by refactoring the priority computation into a small helper function (`_pick_initial_session(sessions, default_from_config, last_for_project)`) and unit-test that helper directly. Prefer this refactor — it makes the logic testable without spinning up Textual.

### Linting

```bash
# No shellcheck needed (Python-only change).
python -c "import ast; ast.parse(open('.aitask-scripts/lib/agent_command_screen.py').read())"
```

## Post-Implementation Reference

See Step 9 (Post-Implementation) in the task-workflow SKILL.md for archival, commit, and push conventions. No worktree cleanup required (working on main directly per `fast` profile).
