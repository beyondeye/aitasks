---
priority: medium
effort: medium
depends: []
issue_type: documentation
status: Ready
labels: [documentation, website]
created_at: 2026-03-26 13:00
updated_at: 2026-03-26 13:00
---

## Context

The t468 task family adds full tmux integration to aitasks TUIs. Child tasks t468_1-t468_5 create shared launch utilities, migrate board/codebrowser to use them, and add tmux settings. This task updates the Hugo/Docsy website documentation to reflect these changes.

Depends on: t468_2 (board migration), t468_3 (codebrowser modal), t468_4 (tmux settings tab)

## Key Areas to Update

### 1. Installation / Setup Documentation
- **tmux as recommended prerequisite**: Add tmux to the recommended tools list, explain why it's the preferred way to run aitasks (groups agent sessions together, no terminal window sprawl)
- Update any "Getting Started" or "Installation" page to mention tmux

### 2. Agent Launching Documentation (pick / explain / qa)
- Document the new `AgentCommandScreen` modal dialog with its two modes:
  - **Direct mode**: Copy command, copy prompt, run in new terminal (existing behavior, now via shared dialog)
  - **tmux mode**: Select/create session, select/create window, split direction toggle
- Explain the tmux launch flow:
  - New session + new window: creates a dedicated tmux session
  - Existing session + new window: adds a window tab to existing session
  - Existing session + existing window: splits into a new pane
- Document keyboard shortcuts in the dialog: `d`/`D` (direct tab), `t` (tmux tab), `c`/`C` (copy cmd), `p`/`P` (copy prompt), `r`/`R` (run), `Escape` (cancel)
- Add screenshots or ASCII mockups of the dialog in both modes

### 3. `ait settings` Documentation
- Document the new "Tmux" tab with its settings:
  - `tmux.default_session` — default tmux session name (default: "aitasks")
  - `tmux.default_split` — default pane split direction: horizontal or vertical
  - `tmux.use_for_create` — whether board's `n` shortcut launches task creation in tmux
- Mention the `t` keyboard shortcut to switch to the Tmux tab in settings

### 4. Board Documentation (`ait board`)
- Update pick task documentation to mention the tmux tab in the modal
- Document `n` shortcut behavior change when `tmux.use_for_create` is enabled
- Mention that the dialog remembers last used session/window within the same TUI session

### 5. Codebrowser Documentation (`ait codebrowser`)
- Document the new launch modal for explain (`e` shortcut) and QA (`a` shortcut in history)
- Both now show the same tabbed dialog with direct/tmux modes

### Reference Files
- `website/content/en/docs/` — Documentation pages
- `.aitask-scripts/lib/agent_command_screen.py` — Dialog implementation (for accurate feature description)
- `.aitask-scripts/lib/agent_launch_utils.py` — Launch utilities (for tmux flow description)
- `.aitask-scripts/settings/settings_app.py` — Settings tab (after t468_4 is done)

## Verification Steps
1. Run `cd website && hugo build --gc --minify` — verify no build errors
2. Run `cd website && ./serve.sh` — preview locally, check all updated pages render correctly
3. Verify internal links between pages are not broken
