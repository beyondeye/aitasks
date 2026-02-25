---
Task: t245_better_organization_of_ait_dispatcher_help_text.md
Worktree: (none — working on current branch)
Branch: main
Base branch: main
---

## Context

The `ait` dispatcher's help text (shown when running `ait` or `ait help`) lists all 17 commands in a flat, unsorted list. Grouping commands by category will improve discoverability.

## Plan

Modify the `show_usage()` function in `ait` (line 18-46) to organize commands into categorical groups with section headers.

### Proposed grouping:

```
Usage: ait <command> [options]

TUI:
  board          Launch the task board TUI
  codebrowser    Launch the code browser TUI

Task Management:
  create         Create a new task file
  ls             List and prioritize tasks
  update         Update task metadata
  sync           Sync task data with remote (push/pull)
  git            Run git commands against task data (worktree-aware)
  lock           Lock/unlock tasks to prevent concurrent work

Integration:
  issue-import   Import tasks from GitHub/GitLab issues
  issue-update   Update/close linked issues

Reporting:
  stats          Show task completion statistics
  changelog      Generate changelog from commits and plans

Tools:
  explain-runs   Manage aiexplain run directories
  zip-old        Archive old completed tasks

Infrastructure:
  setup          Install dependencies
  install        Update aitasks to latest or specific version

Options:
  -h, --help     Show this help message
  -v, --version  Show version

Run 'ait <command> --help' for more information on a command.
```

### File to modify
- `ait` — lines 19-45 (the heredoc inside `show_usage()`)

### Verification
- Run `./ait help` and visually confirm the grouped output

## Final Implementation Notes
- **Actual work done:** Reorganized the `show_usage()` heredoc in `ait` from a flat 17-command list into 6 categories: TUI, Task Management, Integration, Reporting, Tools, Infrastructure
- **Deviations from plan:** None — implemented exactly as planned
- **Issues encountered:** None
- **Key decisions:** User chose TUI as the first section (board + codebrowser), and sync/git/lock under Task Management rather than Infrastructure
