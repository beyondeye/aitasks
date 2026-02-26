---
title: "Command Reference"
linkTitle: "Commands"
weight: 60
description: "Complete CLI reference for all ait subcommands"
---

### Task Management

| Command | Description |
|---------|-------------|
| [`ait create`](task-management/#ait-create) | Create a new task as draft, or finalize drafts (interactive or batch mode) |
| [`ait ls`](task-management/#ait-ls) | List and filter tasks by priority, effort, status, labels |
| [`ait update`](task-management/#ait-update) | Update task metadata (status, priority, labels, etc.) |
| [`ait sync`](sync/) | Sync task data with remote (push/pull) |
| [`ait git`](sync/) | Run git commands against task data (worktree-aware) |
| [`ait lock`](lock/) | Lock/unlock tasks to prevent concurrent work |

### TUI

| Command | Description |
|---------|-------------|
| [`ait board`](board-stats/#ait-board) | Open the kanban-style TUI board |
| [`ait codebrowser`](board-stats/#ait-codebrowser) | Launch the code browser TUI |

### Integration

| Command | Description |
|---------|-------------|
| [`ait issue-import`](issue-integration/#ait-issue-import) | Import tasks from GitHub/GitLab/Bitbucket issues |
| [`ait issue-update`](issue-integration/#ait-issue-update) | Update or close linked GitHub/GitLab/Bitbucket issues |

### Reporting

| Command | Description |
|---------|-------------|
| [`ait stats`](board-stats/#ait-stats) | Show task completion statistics |
| [`ait changelog`](issue-integration/#ait-changelog) | Gather changelog data from commits and archived plans |

### Tools

| Command | Description |
|---------|-------------|
| [`ait explain-runs`](explain/#ait-explain-runs) | Manage aiexplain run directories (list, delete, cleanup) |
| [`ait explain-cleanup`](explain/#ait-explain-cleanup) | Remove stale aiexplain run directories |
| [`ait zip-old`](issue-integration/#ait-zip-old) | Archive old completed task and plan files |

### Infrastructure

| Command | Description |
|---------|-------------|
| [`ait setup`](setup-install/#ait-setup) | Install/update dependencies and configure Claude Code permissions |
| [`ait install`](setup-install/#ait-install) | Update aitasks to latest or specific version |

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
ait codebrowser                         # Open code browser TUI
ait issue-import                        # Import issues from issue tracker
ait lock 42                             # Pre-lock a task before Claude Web
ait lock --list                         # See all active locks
ait lock --unlock 42                    # Release a lock
ait sync                               # Interactive sync with progress
ait sync --batch                        # Batch mode for scripting
ait git add aitasks/t42.md              # Git operations on task data
ait stats                               # Show completion stats
ait explain-runs --list                  # List all explain runs
ait explain-runs --cleanup-stale         # Remove stale runs
ait explain-cleanup --dry-run --all      # Preview stale cleanup
ait install                              # Update to latest version
ait install 0.2.1                        # Install specific version
ait --version                           # Show installed version
```

---

**Next:** [Development Guide]({{< relref "development" >}})
