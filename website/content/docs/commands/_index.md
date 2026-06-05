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
| [`ait git-health`](sync/#ait-git-health) | Diagnose the `.aitask-data` worktree state (detached HEAD, stuck rebase/merge) |
| [`ait lock`](lock/) | Lock/unlock tasks to prevent concurrent work |

### TUI

| Command | Description |
|---------|-------------|
| [`ait board`](board-stats/#ait-board) | Open the kanban-style TUI board |
| [`ait codebrowser`](board-stats/#ait-codebrowser) | Launch the code browser TUI |
| [`ait monitor`](../tuis/monitor/) | Dashboard of every code-agent and TUI pane across all aitasks tmux sessions |
| [`ait minimonitor`](../tuis/minimonitor/) | Narrow sidebar variant of monitor for tmux agent panes |
| [`ait applink`](../tuis/applink/) | Pair the mobile companion app to your workspace over LAN (QR bootstrap) |
| [`ait stats-tui`](../tuis/stats/) | Pane-based viewer for archived task completion statistics |
| [`ait ide`](../installation/terminal-setup/) | Start (or attach to) the configured tmux session and launch `ait monitor` — one view of a shared session; see `ait ide --help` |
| [`ait settings`](../tuis/settings/) | Open the settings TUI for configuration management |
| [`ait syncer`](../tuis/syncer/) | Open the remote-desync syncer TUI for `main` and `aitask-data` |

### Integration

| Command | Description |
|---------|-------------|
| [`ait issue-import`](issue-integration/#ait-issue-import) | Import tasks from GitHub/GitLab/Bitbucket issues |
| [`ait issue-update`](issue-integration/#ait-issue-update) | Update or close linked GitHub/GitLab/Bitbucket issues |
| [`ait pr-import`](pr-import/#ait-pr-import) | Import pull requests as tasks or extract PR data for AI analysis |

### Cross-repo

| Command | Description |
|---------|-------------|
| [`ait projects`](../workflows/multi_project/#the-ait-projects-command) | Manage the linked-project registry (`list`, `add`, `remove`, `update`, `prune`, `doctor`, `resolve`, `exec`) — see [Multi-Project](../workflows/multi_project/) and [Cross-Project Dependencies](../workflows/cross_project_dependencies/) |

### Agent Orchestration

| Command | Description |
|---------|-------------|
| [`ait crew`](crew/) | Initialize and run multi-agent crews — `init`, `addwork`, `setmode`, `status`, `command`, `runner`, `report`, `cleanup`, `dashboard`, `logview` (see [Agentcrews](../concepts/agentcrews/)) |

### Reporting

| Command | Description |
|---------|-------------|
| [`ait stats`](board-stats/#ait-stats) | Show task completion statistics |
| [`ait changelog`](issue-integration/#ait-changelog) | Gather changelog data from commits and archived plans |

### Tools

| Command | Description |
|---------|-------------|
| [`ait codeagent`](codeagent/) | Manage code agent and model configuration |
| [`ait skillrun`](../concepts/skill-templating/#invocation-paths) | Launch a code agent with a profile-aware aitask skill |
| [`ait explain-runs`](explain/#ait-explain-runs) | Manage aitask-explain run directories (list, delete, cleanup) |
| [`ait explain-cleanup`](explain/#ait-explain-cleanup) | Remove stale aitask-explain run directories |
| [`ait zip-old`](issue-integration/#ait-zip-old) | Archive old completed task and plan files into `tar.zst` bundles — periodic maintenance ([guide](../workflows/repo-maintenance/)) |

### Infrastructure

| Command | Description |
|---------|-------------|
| [`ait setup`](setup-install/#ait-setup) | Install/update dependencies and configure Claude Code permissions |
| [`ait upgrade`](setup-install/#ait-upgrade) | Update aitasks to latest or specific version |

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
ait monitor                             # Dashboard of all agent/TUI panes
ait projects list                       # List registered linked projects
ait skillrun pick --profile fast 42     # Launch a code agent on task 42
ait crew init --id sprint1 --batch      # Initialize a multi-agent crew
ait git-health                          # Diagnose the .aitask-data worktree
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
ait codeagent list-agents                 # Show available code agents
ait codeagent list-models claudecode      # List Claude models
ait codeagent resolve task-pick           # Show configured agent/model
ait settings                              # Open settings TUI
ait upgrade                              # Update to latest version
ait upgrade 0.2.1                        # Upgrade to specific version
ait --version                           # Show installed version
```

---

**See also:** [Repository Maintenance]({{< relref "/docs/workflows/repo-maintenance" >}}) for periodic upkeep commands (`zip-old`, explain cleanup, `changelog`, `git-health`, `upgrade`), and [Multi-Project]({{< relref "/docs/workflows/multi_project" >}}) for the cross-repo `ait projects` workflow.

**Next:** [Development Guide]({{< relref "development" >}})
