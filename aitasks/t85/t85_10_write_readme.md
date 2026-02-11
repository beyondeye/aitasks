---
priority: medium
effort: low
depends: [t85_2, t85_5, t85_7]
issue_type: feature
status: Implementing
labels: [bash, aitasks]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-02-11 10:00
updated_at: 2026-02-11 14:58
---

## Context

This is child task 10 of parent task t85 (Cross-Platform aitask Framework Distribution). The `beyondeye/aitasks` GitHub repo needs a comprehensive README.md with installation instructions, command reference, and platform support information.

**File to create**: `~/Work/aitasks/README.md`

## What to Do

### Write README.md with the following sections

#### 1. Header and description

Title: `aitasks` — a brief tagline like "AI-powered task management framework for Claude Code projects".

Short description: File-based task management system that integrates with Claude Code via skills. Tasks are markdown files with YAML frontmatter, organized in a kanban-style workflow. Includes a Python TUI board, GitHub issue integration, and completion statistics.

#### 2. Quick Install

The one-liner:
```bash
curl -fsSL https://raw.githubusercontent.com/beyondeye/aitasks/main/install.sh | bash
```

Or with force (for upgrades):
```bash
curl -fsSL https://raw.githubusercontent.com/beyondeye/aitasks/main/install.sh | bash -s -- --force
```

#### 3. What gets installed

Explain the two-part installation:

**Per-project files** (committed to your repo):
- `ait` — CLI dispatcher
- `aiscripts/` — Framework scripts
- `.claude/skills/aitask-*` — Claude Code skill definitions
- `aitasks/` — Task data directory (auto-created)
- `aiplans/` — Implementation plans directory (auto-created)

**Global dependencies** (installed once per machine):
- CLI tools: `fzf`, `gh`, `jq`, `git`
- Python venv at `~/.aitask/venv/` with `textual`, `pyyaml`, `linkify-it-py`
- Global `ait` shim at `~/.local/bin/ait`

#### 4. Command Reference

Table of all commands:

| Command | Description |
|---------|-------------|
| `ait create` | Create a new task (interactive or batch mode) |
| `ait ls` | List and filter tasks by priority, effort, status, labels |
| `ait update` | Update task metadata (status, priority, labels, etc.) |
| `ait import` | Import GitHub issues as tasks |
| `ait board` | Open the kanban-style TUI board |
| `ait stats` | Show task completion statistics |
| `ait clear-old` | Archive old completed task/plan files |
| `ait issue-update` | Update/close linked GitHub issues |
| `ait setup` | Install/update dependencies |
| `ait --version` | Show installed version |
| `ait help` | Show command list |

Include a few usage examples:
```bash
ait create                           # Interactive task creation
ait create --batch --name "fix_bug"  # Batch mode
ait ls -v 15                         # List top 15 tasks verbose
ait ls -v -l ui,frontend 10          # Filter by labels
ait update --batch 42 --status Done  # Mark task done
ait board                            # Open TUI board
ait import                           # Import GitHub issues
```

#### 5. Claude Code Integration

Explain the Claude Code skills:

- `/aitask-pick` — Select and implement the next task (full workflow with planning, branching, implementation)
- `/aitask-create` — Create tasks interactively via Claude Code's AskUserQuestion
- `/aitask-create2` — Create tasks using terminal fzf (faster)
- `/aitask-stats` — View completion statistics
- `/aitask-cleanold` — Archive old files

#### 6. Platform Support

| Platform | Status | Notes |
|----------|--------|-------|
| Arch Linux | Fully supported | Primary development platform |
| Ubuntu/Debian | Fully supported | Includes WSL |
| Fedora/RHEL | Fully supported | |
| macOS | Partial | `date -d` and bash 3.2 limitations (see Known Issues) |
| Windows (WSL) | Fully supported | Via WSL Ubuntu |

#### 7. Task File Format

Brief example of a task markdown file with YAML frontmatter:
```yaml
---
priority: high
effort: medium
depends: []
issue_type: feature
status: Ready
labels: [ui, backend]
created_at: 2026-01-15 10:00
updated_at: 2026-01-15 10:00
---

## Task description here

Detailed description of what needs to be done.
```

Mention status workflow: Ready → Editing → Implementing → Done → Archived

#### 8. Known Issues

- **macOS `date -d`**: The `ait stats` and `ait import` commands use GNU `date -d` which doesn't work with macOS BSD date. Install `coreutils` via Homebrew for `gdate` as a workaround.
- **macOS bash**: System bash is v3.2; aitasks requires bash 4+. `ait setup` installs bash 5 via Homebrew.

#### 9. Development / Contributing

- How to modify scripts
- How to test changes
- Release process: update VERSION, tag, push

### Commit

```bash
cd ~/Work/aitasks
git add README.md
git commit -m "Add comprehensive README with install and usage docs"
```

## Verification

1. README.md renders correctly on GitHub (check markdown formatting)
2. The curl install command URL is correct: `https://raw.githubusercontent.com/beyondeye/aitasks/main/install.sh`
3. All 10 `ait` subcommands are documented
4. Platform support matrix is accurate
