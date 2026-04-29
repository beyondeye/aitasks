---
priority: medium
effort: medium
depends: [t713_5]
issue_type: documentation
status: Ready
labels: [documentation, tui]
created_at: 2026-04-29 10:56
updated_at: 2026-04-29 10:56
---

## Context

Parent t713 adds a new `ait syncer` command and several visible integrations. This child updates the website documentation everywhere affected and adds a dedicated Syncer TUI page.

Docs must describe current behavior only. Do not frame the work as a correction to earlier docs or discuss historical behavior.

## Key Files to Modify

- `website/`: update relevant command, TUI, tmux, and configuration documentation pages.
- Website navigation/sidebar files: add the dedicated Syncer TUI page in the appropriate TUI section.
- Any generated or indexed command reference files if this repo maintains them manually.

## Reference Files for Patterns

- Existing website pages for board, monitor, minimonitor, settings, stats, or codebrowser TUIs.
- Existing docs for `ait sync`, tmux integration, and project configuration.
- `CLAUDE.md` Documentation Writing section: describe current state only.

## Implementation Plan

1. Locate existing website pages that mention:
   - `ait sync`.
   - TUI switcher shortcuts.
   - tmux/`ait ide` startup.
   - monitor or minimonitor behavior.
   - `project_config.yaml` / `tmux` settings.
2. Add a dedicated Syncer TUI page covering:
   - Purpose: visible remote desync tracking for source code and task data.
   - Command: `ait syncer`.
   - Branch rows: `main` and `aitask-data` only.
   - Polling/refresh behavior.
   - Task-data sync relationship to existing `ait sync`.
   - Pull/push actions and failure handling.
   - TUI switcher key `y`.
   - `ait ide` autostart via `tmux.syncer.autostart`.
3. Update affected docs to cross-link to the Syncer TUI page.
4. Keep wording concise and operational; avoid implementation-history notes.
5. Ensure navigation/sidebar includes the new page.

## Verification Steps

- Run the repo’s website build command, usually from `website/` with `hugo build --gc --minify` if dependencies are available.
- If full build dependencies are missing, run the highest-signal available static check and document the limitation.
- Manually inspect website navigation to confirm the Syncer TUI page is reachable.
