---
priority: medium
effort: medium
depends: []
issue_type: feature
status: Implementing
labels: [tmux, aitask_monitor, tui_switcher]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-04-23 20:20
updated_at: 2026-04-23 21:53
---

## Context

Foundational child of t634. Before multi-session monitor (t634_2) and two-level switcher (t634_3) can be implemented, the framework needs two shared primitives that both will call into:

1. A way to enumerate "aitasks-like" tmux sessions on the current server (not every random session the user has running).
2. A cross-session focus helper that jumps the attached tmux client to a pane anywhere on the server.

This task delivers both in `.aitask-scripts/lib/agent_launch_utils.py` (the natural home — t632 already added `tmux_session_target` / `tmux_window_target` / `find_window_by_name` there) plus unit tests.

## Key Files to Modify

- `.aitask-scripts/lib/agent_launch_utils.py` — add `discover_aitasks_sessions()`, `switch_to_pane_anywhere()`, and supporting data class(es).
- `tests/test_multi_session_primitives.sh` — new; exercise discovery heuristics against a mocked tmux server (isolated via `TMUX_TMPDIR`, same pattern as `tests/test_tmux_exact_session_targeting.sh`).

## Reference Files for Patterns

- `tests/test_tmux_exact_session_targeting.sh` — `TMUX_TMPDIR` isolation, skip-on-no-tmux, helper-string + runtime assertions. Copy this layout.
- `.aitask-scripts/lib/agent_launch_utils.py:load_tmux_defaults` — how to read `project_config.yaml`. Same loader pattern will confirm a session's project root.
- `.aitask-scripts/monitor/tmux_monitor.py:discover_panes` — how the current monitor enumerates panes server-wide with `list-panes -s`. Reuse the output format.

## Implementation Plan

### Step 1 — `AitasksSession` dataclass

```python
@dataclass(frozen=True)
class AitasksSession:
    session: str          # tmux session name
    project_root: Path    # absolute path to the project root
    project_name: str     # basename(project_root), for display
```

### Step 2 — `discover_aitasks_sessions() -> list[AitasksSession]`

Heuristic (apply in order until one matches per session):

1. Iterate `tmux list-sessions -F '#{session_name}'`. For each session, list its panes and read `#{pane_current_path}` for each.
2. For each candidate pane path, walk up until an ancestor contains `aitasks/metadata/project_config.yaml`. First hit wins for that session.
3. **Fallback** for sessions with no pane in an aitasks project (e.g. a fresh session with just a shell): check whether the session name matches a known project's `tmux.default_session` — maintained via an **in-process registry** that any running aitasks TUI writes to when it starts (see Step 4). If no registry hit, the session is not aitasks-like.
4. Return the list deduped by session.

Cache the result for the duration of one enumerate call — callers who want fresh data call `discover_aitasks_sessions()` again (no module-level TTL cache, to avoid staleness drift in a long-running monitor).

**Decision point to raise during implementation**: should the registry in step 3 persist across tmux restarts (e.g. `~/.aitask/sessions.json`) or be tmux-server-lifetime only (e.g. via `tmux set-environment -g AITASKS_REGISTRY`)? The server-lifetime option is simpler; the persistent option survives `tmux kill-server`. Recommend server-lifetime via a global tmux env var updated by `ait ide` on startup.

### Step 3 — `switch_to_pane_anywhere(pane_id: str) -> bool`

```python
def switch_to_pane_anywhere(pane_id: str) -> bool:
    """Teleport the attached tmux client to the given pane, regardless of session.

    Resolves session and window_index from the pane_id via `display-message`,
    then runs switch-client + select-window + select-pane. Pane IDs are
    server-globally unique, so no extra session hint is required.

    Returns True on success, False if tmux is unavailable or the pane is dead.
    """
```

Implementation:

```
sess=$(tmux display-message -p -t <pane_id> '#{session_name}')
win=$(tmux display-message -p -t <pane_id> '#{window_index}')
tmux switch-client -t "=$sess"
tmux select-window -t "=$sess:$win"
tmux select-pane -t "<pane_id>"
```

Three separate calls so each can fail cleanly; log-or-return-False on any non-zero.

### Step 4 — Registry hook in `ait ide`

Minimal: on startup, after resolving the session, run:

```bash
tmux set-environment -g "AITASKS_PROJECT_$SESSION" "$(pwd)"
```

(Name spaced per session so multiple concurrent `ait ide` invocations don't collide.)

`discover_aitasks_sessions()` reads `tmux show-environment -g` and parses entries prefixed `AITASKS_PROJECT_` to find registered project roots for sessions that didn't match via pane-cwd.

**Alternative considered**: writing to a file in `~/.aitask/`. Rejected because tmux server-env cleans itself on `kill-server`, whereas a file would need explicit cleanup.

## Verification

Automated (`tests/test_multi_session_primitives.sh`):

- `AitasksSession` dataclass fields match spec.
- `switch_to_pane_anywhere` with tmux absent returns False (no crash).
- With an isolated `TMUX_TMPDIR`:
  - Start session A in a temp dir containing `aitasks/metadata/project_config.yaml`; `discover_aitasks_sessions()` returns `[AitasksSession("A", <path>, "<basename>")]`.
  - Start session B in `/tmp` (no aitasks metadata); it is NOT returned.
  - Export `AITASKS_PROJECT_B=<temp_aitasks_path>`; now session B IS returned (registry fallback).
  - `switch_to_pane_anywhere(<pane_id from B>)` succeeds (check via `tmux display-message -p "#S"` inside the attached client … or more pragmatically, verify the three tmux calls were issued in order by capturing a wrapper stub).

## Gotchas to address during implementation

- macOS `tmux display-message -p -t <pane>` works fine but be careful with shell quoting in tests (use exec lists via subprocess.run).
- `tmux show-environment -g` output format: `VAR=value` one per line, with `-VAR` for unset markers. Already handled by the codebrowser focus reader in `codebrowser_app.py` — crib from there.
- `tmux set-environment -g` persists for the server lifetime. If `ait ide` is run from inside tmux (current-session path), the set-environment call should still run (the function returns early for nested tmux today, so this needs a small rearrangement in `aitask_ide.sh`).
- When `pane_current_path` is a subdirectory of the aitasks repo (e.g. inside `aiplans/`), the walk-up still finds `aitasks/metadata/` — `Path.is_file()` on each ancestor. No special casing needed.
- Detection must tolerate dead panes / destroyed sessions between listing and cwd-reading (tmux is a live system). Wrap the per-pane `display-message` in try/except and skip on failure.
