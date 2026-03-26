---
priority: medium
effort: medium
depends: [t468_1, t468_4]
issue_type: feature
status: Ready
labels: [ui, tmux]
created_at: 2026-03-26 13:06
updated_at: 2026-03-26 13:06
---

## Context

The t468 task family adds tmux integration to aitasks. With shared launch utilities (t468_1), tmux settings (t468_4), and all TUIs migrated (t468_2, t468_3), the next step is making it easy to run aitasks TUIs inside a tmux session automatically — so the user gets a pre-configured workspace with board, codebrowser, and settings grouped together.

Depends on: t468_1 (shared utilities), t468_4 (tmux settings)

## Goals

1. **Auto-launch TUIs in tmux session**: When tmux is available and a setting is enabled, `ait board`, `ait codebrowser`, and `ait settings` should automatically start inside the configured aitasks tmux session (each as its own window)
2. **`ait workspace` command**: A new convenience command that launches a tmux session pre-populated with the main TUIs (board, codebrowser) in separate windows — a one-command workspace setup

## Design Considerations (to refine during planning)

### Option A: `ait` dispatcher integration
- Modify the `ait` bash dispatcher to detect tmux availability
- If `tmux.auto_session` is enabled in settings and we're NOT already inside the aitasks tmux session:
  - Create the session if it doesn't exist
  - Launch the TUI command inside a new tmux window in that session
  - Attach to the session
- If already inside the aitasks session: run normally (avoid infinite recursion)
- Detection: check `$TMUX` env + `tmux display-message -p '#{session_name}'` to see if we're already in the right session

### Option B: `ait workspace` standalone command
- New script: `.aitask-scripts/aitask_workspace.sh`
- Creates a tmux session with a sensible layout:
  - Window 1: `ait board` (named "board")
  - Window 2: `ait codebrowser` (named "codebrowser")
  - Optional Window 3: terminal for manual commands
- If session already exists, attaches to it
- Idempotent: re-running just attaches, doesn't duplicate windows

### Option C: Both A and B
- `ait workspace` for explicit full-workspace setup
- `ait board` etc. auto-launch in session when configured (lighter touch)

### Settings to add (in t468_4's tmux settings tab)
- `tmux.auto_session` — whether `ait board`/`ait codebrowser`/`ait settings` auto-launch in tmux session (default: false)
- `tmux.workspace_layout` — which TUIs to include in `ait workspace` (default: "board,codebrowser")

## Key Files to Modify

1. **`ait`** — Main bash dispatcher (for auto-session detection/routing)
2. **`.aitask-scripts/aitask_workspace.sh`** — New script for `ait workspace` command
3. **`.aitask-scripts/lib/agent_launch_utils.py`** — May need helper for "am I in the aitasks session?" check

## Reference Files
- `ait` — Current dispatcher structure
- `.aitask-scripts/lib/agent_launch_utils.py` — `is_tmux_available()`, `get_tmux_sessions()`, `load_tmux_defaults()`
- `aitasks/metadata/project_config.yaml` — tmux settings section

## Verification Steps
1. Run `ait workspace` — verify tmux session created with board + codebrowser windows
2. Run `ait workspace` again — verify it attaches to existing session (no duplicates)
3. Enable `tmux.auto_session`, run `ait board` outside tmux — verify it launches inside aitasks session
4. Run `ait board` while already inside aitasks session — verify it runs normally (no recursion)
5. Run `ait board` with tmux not installed — verify normal behavior
