# aitasks

AI-powered task management framework for Claude Code projects.

A file-based task management system that integrates with [Claude Code](https://docs.anthropic.com/en/docs/claude-code) via skills. Tasks are markdown files with YAML frontmatter, organized in a kanban-style workflow. Includes a Python TUI board, GitHub issue integration, and completion statistics.

## Quick Install

Install into your project directory:

```bash
curl -fsSL https://raw.githubusercontent.com/beyondeye/aitasks/main/install.sh | bash
```

Upgrade an existing installation:

```bash
curl -fsSL https://raw.githubusercontent.com/beyondeye/aitasks/main/install.sh | bash -s -- --force
```

## What Gets Installed

**Per-project files** (committed to your repo):

- `ait` — CLI dispatcher script
- `aiscripts/` — Framework scripts (task management, board, stats, etc.)
- `.claude/skills/aitask-*` — Claude Code skill definitions
- `aitasks/` — Task data directory (auto-created)
- `aiplans/` — Implementation plans directory (auto-created)

**Global dependencies** (installed once per machine via `ait setup`):

- CLI tools: `fzf`, `gh`, `jq`, `git`
- Python venv at `~/.aitask/venv/` with `textual`, `pyyaml`, `linkify-it-py`
- Global `ait` shim at `~/.local/bin/ait`

## Command Reference

| Command | Description |
|---------|-------------|
| `ait create` | Create a new task (interactive or batch mode) |
| `ait ls` | List and filter tasks by priority, effort, status, labels |
| `ait update` | Update task metadata (status, priority, labels, etc.) |
| `ait issue-import` | Import tasks from GitHub/GitLab issues |
| `ait board` | Open the kanban-style TUI board |
| `ait stats` | Show task completion statistics |
| `ait clear-old` | Archive old completed task and plan files |
| `ait issue-update` | Update or close linked GitHub/GitLab issues |
| `ait setup` | Install/update dependencies |

### Usage Examples

```bash
ait create                              # Interactive task creation
ait create --batch --name "fix_bug"     # Batch mode
ait ls -v 15                            # List top 15 tasks (verbose)
ait ls -v -l ui,frontend 10             # Filter by labels
ait update --batch 42 --status Done     # Mark task done
ait board                               # Open TUI board
ait issue-import                        # Import GitHub issues
ait stats                               # Show completion stats
ait --version                           # Show installed version
```

## Claude Code Integration

aitasks provides Claude Code skills that automate the full task workflow:

| Skill | Description |
|-------|-------------|
| `/aitask-pick` | Select and implement the next task (planning, branching, implementation, archival) |
| `/aitask-create` | Create tasks interactively via Claude Code |
| `/aitask-create2` | Create tasks using terminal fzf (faster alternative) |
| `/aitask-stats` | View completion statistics |
| `/aitask-cleanold` | Archive old completed files |

The `/aitask-pick` skill provides a full development workflow: task selection, plan mode integration, optional worktree/branch creation, implementation tracking, user review, and post-implementation archival.

### Execution Profiles

The `/aitask-pick` skill asks several interactive questions before reaching implementation (email, local/remote, worktree, plan handling, etc.). Execution profiles let you pre-configure answers to these questions so you can go from task selection to implementation with minimal input.

Profiles are YAML files stored in `aitasks/metadata/profiles/`. Two profiles ship by default:

- **default** — All questions asked normally (empty profile, serves as template)
- **fast** — Skip confirmations, use first stored email, work locally on current branch, reuse existing plans

When you run `/aitask-pick`, the profile is selected first (Step 0a). If only one profile exists, it's auto-loaded. With multiple profiles, you're prompted to choose.

#### Profile Settings

| Key | Type | Description |
|-----|------|-------------|
| `name` | string (required) | Display name shown during profile selection |
| `description` | string (required) | Description shown below profile name during selection |
| `skip_task_confirmation` | bool | `true` = auto-confirm task selection |
| `default_email` | string | `"first"` = use first email from emails.txt; or a literal email address |
| `run_location` | string | `"locally"` or `"remotely"` |
| `create_worktree` | bool | `true` = create worktree; `false` = work on current branch |
| `base_branch` | string | Branch name for worktree (e.g., `"main"`) |
| `plan_preference` | string | `"use_current"`, `"verify"`, or `"create_new"` |
| `post_plan_action` | string | `"start_implementation"` = skip post-plan prompt |

Omitting a key means the corresponding question is asked interactively. Plan approval (ExitPlanMode) is always mandatory and cannot be skipped.

#### Creating a Custom Profile

```bash
cp aitasks/metadata/profiles/fast.yaml aitasks/metadata/profiles/my-profile.yaml
```

Edit the file to set your preferences:

```yaml
name: worktree
description: Like fast but creates a worktree on main for each task
skip_task_confirmation: true
default_email: first
run_location: locally
create_worktree: true
base_branch: main
plan_preference: use_current
post_plan_action: start_implementation
```

Profiles are preserved during `install.sh --force` upgrades (existing files are not overwritten).

## Platform Support

| Platform | Status | Notes |
|----------|--------|-------|
| Arch Linux | Fully supported | Primary development platform |
| Ubuntu/Debian | Fully supported | Includes Pop!_OS, Linux Mint, Elementary |
| Fedora/RHEL | Fully supported | Includes CentOS, Rocky, Alma |
| macOS | Partial | `date -d` and bash 3.2 limitations (see Known Issues) |
| Windows (WSL) | Fully supported | Via WSL with Ubuntu/Debian |

## Task File Format

Tasks are markdown files with YAML frontmatter in the `aitasks/` directory:

```yaml
---
priority: high
effort: medium
depends: []
issue_type: feature  # See aitasks/metadata/task_types.txt for valid types
status: Ready
labels: [ui, backend]
created_at: 2026-01-15 10:00
updated_at: 2026-01-15 10:00
---

## Task description here

Detailed description of what needs to be done.
```

**Status workflow:** Ready → Editing → Implementing → Done → Archived

Tasks support parent-child hierarchies for breaking complex work into subtasks. Child tasks live in `aitasks/t<parent>/` subdirectories.

### Customizing Task Types

Valid issue types are defined in `aitasks/metadata/task_types.txt` (one type per line, sorted alphabetically). The default types are:

```
bug
feature
refactor
```

To add a custom type, simply add a new line to the file. All scripts (`ait create`, `ait update`, `ait board`, `ait stats`) read from this file dynamically.

## Known Issues

- **macOS `date -d`**: The `ait stats` and `ait issue-import` commands use GNU `date -d` which is not available with macOS BSD date. Install `coreutils` via Homebrew (`brew install coreutils`) to get `gdate` as a workaround.
- **macOS bash**: The system bash on macOS is v3.2; aitasks requires bash 4+. Running `ait setup` on macOS installs bash 5 via Homebrew.

## Development

### Modifying scripts

All framework scripts live in `aiscripts/`. The `ait` dispatcher forwards subcommands to the corresponding `aitask_*.sh` script. Claude Code skills are defined in `.claude/skills/`.

### Testing changes

Run individual commands to verify:

```bash
./ait --version          # Check dispatcher works
./ait ls -v 5            # List tasks
./ait setup              # Re-run dependency setup
bash -n aiscripts/*.sh   # Syntax-check all scripts
```

### Release process

1. Update the `VERSION` file
2. Commit and tag: `git tag v<version>`
3. Push with tags: `git push && git push --tags`
4. GitHub Actions builds the release tarball automatically

## License

See [LICENSE](LICENSE) for details.
