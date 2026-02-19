---
title: "Command Reference"
linkTitle: "Commands"
weight: 60
description: "Complete CLI reference for all ait subcommands"
---

| Command | Description |
|---------|-------------|
| [`ait setup`](setup-install/#ait-setup) | Install/update dependencies and configure Claude Code permissions |
| [`ait install`](setup-install/#ait-install) | Update aitasks to latest or specific version |
| [`ait create`](task-management/#ait-create) | Create a new task as draft, or finalize drafts (interactive or batch mode) |
| [`ait ls`](task-management/#ait-ls) | List and filter tasks by priority, effort, status, labels |
| [`ait update`](task-management/#ait-update) | Update task metadata (status, priority, labels, etc.) |
| [`ait board`](board-stats/#ait-board) | Open the kanban-style TUI board |
| [`ait stats`](board-stats/#ait-stats) | Show task completion statistics |
| [`ait zip-old`](issue-integration/#ait-zip-old) | Archive old completed task and plan files |
| [`ait issue-import`](issue-integration/#ait-issue-import) | Import tasks from GitHub/GitLab issues |
| [`ait issue-update`](issue-integration/#ait-issue-update) | Update or close linked GitHub/GitLab issues |
| [`ait changelog`](issue-integration/#ait-changelog) | Gather changelog data from commits and archived plans |

## Usage Examples

```bash
ait setup                               # Install dependencies
ait create                              # Interactive task creation (draft workflow)
ait create --batch --name "fix_bug"     # Create draft (no network needed)
ait create --batch --name "fix_bug" --commit  # Create and finalize immediately
ait create --batch --finalize-all       # Finalize all draft tasks
ait ls -v 15                            # List top 15 tasks (verbose)
ait ls -v -l ui,frontend 10             # Filter by labels
ait update --batch 42 --status Done     # Mark task done
ait board                               # Open TUI board
ait issue-import                        # Import GitHub issues
ait stats                               # Show completion stats
ait install                              # Update to latest version
ait install 0.2.1                        # Install specific version
ait --version                           # Show installed version
```
