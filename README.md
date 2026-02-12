# aitasks

AI-powered task management framework for Claude Code projects.

A file-based task management system that integrates with [Claude Code](https://docs.anthropic.com/en/docs/claude-code) via skills. Tasks are markdown files with YAML frontmatter, organized in a kanban-style workflow. Includes a Python TUI board, GitHub issue integration, and completion statistics.

Built for maximizing development speed 🚀 AND human-to-agent intent transfer efficiency 💬.

Inspired by [Conductor](https://github.com/gemini-cli-extensions/conductor), and [beads](https://github.com/steveyegge/beads)

## The challenge
AI coding agents has reached a proficiency level where, given correct specs and intent, are almost always capable of handling a code-development task. The challenge is the transfer of intent from developer/designer to the AI agent. The challenge is two-fold:
  1) Transfer intent in a structured way that optimize context building for the AI agent
  2) Maximize speed so that the human in the loop does not become the bottle-neck for development speed

## Core Philosophy
"Light Spec" engine: Unlike rigid Spec-Driven Development (e.g., [Speckit](https://github.com/github/spec-kit), tasks here are living documents:
  - Raw Intent: A task starts as a simple Markdown file capturing the goal.
  - Iterative Refinement: An included AI workflow refines task files in stages—expanding context, adding technical details, and verifying requirements—before code is written.

## Key Features & Architecture
- Repository-Centric (Inspired by Conductor)
  - Tasks as Files: Every task is a Markdown file stored within the code repository.

  - Self-Contained Metadata: Unlike Conductor, task metadata (status, priority, assignee) is stored directly in the file's YAML frontmatter.

- Daemon-less & Stateless (The Beads Evolution) No Infrastructure: No SQL backend, no background daemons. Just files and scripts.

- Remote-Ready: Because the state is entirely in the file system, it works seamlessly in remote AI-agent sessions.

- Dual-Mode CLI tools optimized for two distinct users:
  - Interactive Mode (For Humans): Optimized for "Flow." Rapidly create, edit, and prioritize tasks without context switching.
  - Batch Mode (For Agents): allowing AI agents to read specs, create tasks and update task status programmatically.

- Hierarchical Execution
  - Task Dependencies: Define task/task and task parent/task child relationships.

  - Agent Decomposition: If a task is too risky or complex for a single run, the Agent can "explode" a parent task into child files.

  - Parallelism: thanks to task status stored in git, and AI agents workflow that support git worktrees.

- Visual Management
TUI Board: A terminal-based visual interface (Kanban style) for visualizing and organizing tasks without leaving the terminal.

- Battle tested:
Not a research experiment. actively developed and used in real projects

- Claude Code optimized.

- Fully customizable workflow for each project:  all the scripts and workflow skills live in you project repo: modify it for your needs. You will still be able to merge new features and cabilities as they are added to the framework, with the included AI agent-based framework update skill.

## Platform Support

| Platform | Status | Notes |
|----------|--------|-------|
| Arch Linux | Fully supported | Primary development platform |
| Ubuntu/Debian | Fully supported | Includes Pop!_OS, Linux Mint, Elementary |
| Fedora/RHEL | Fully supported | Includes CentOS, Rocky, Alma |
| macOS | Partial | `date -d` and bash 3.2 limitations (see [Known Issues](#known-issues)) |
| Windows (WSL) | Fully supported | Via WSL with Ubuntu/Debian |

## Known Issues

- **macOS `date -d`**: The `ait stats` and `ait issue-import` commands use GNU `date -d` which is not available with macOS BSD date. Install `coreutils` via Homebrew (`brew install coreutils`) to get `gdate` as a workaround.
- **macOS bash**: The system bash on macOS is v3.2; aitasks requires bash 4+. Running `ait setup` on macOS installs bash 5 via Homebrew.

## Quick Install

Install into your project directory:

```bash
curl -fsSL https://raw.githubusercontent.com/beyondeye/aitasks/main/install.sh | bash
```

Upgrade an existing installation:

```bash
ait install latest
```

Or for fresh installs without an existing `ait` dispatcher:

```bash
curl -fsSL https://raw.githubusercontent.com/beyondeye/aitasks/main/install.sh | bash -s -- --force
```

After installing, run `ait setup` to install dependencies and configure Claude Code permissions. See [`ait setup`](#ait-setup) for details.

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
- Claude Code permissions in `.claude/settings.local.json` (see [Claude Code Permissions](#claude-code-permissions))

## Table of Contents

- [Command Reference](#command-reference)
  - [Usage Examples](#usage-examples)
  - [ait setup](#ait-setup)
  - [ait install](#ait-install)
  - [ait create](#ait-create)
  - [ait ls](#ait-ls)
  - [ait update](#ait-update)
  - [ait board](#ait-board)
  - [ait stats](#ait-stats)
  - [ait clear-old](#ait-clear-old)
  - [ait issue-import](#ait-issue-import)
  - [ait issue-update](#ait-issue-update)
  - [ait changelog](#ait-changelog)
- [Claude Code Integration](#claude-code-integration)
  - [/aitask-pick](#aitask-pick-number)
  - [/aitask-create](#aitask-create)
  - [/aitask-create2](#aitask-create2)
  - [/aitask-stats](#aitask-stats)
  - [/aitask-cleanold](#aitask-cleanold)
  - [/aitask-changelog](#aitask-changelog)
- [Task File Format](#task-file-format)
  - [Customizing Task Types](#customizing-task-types)
- [Development](#development)
  - [Architecture](#architecture)
  - [Library Scripts](#library-scripts)
  - [Modifying scripts](#modifying-scripts)
  - [Testing changes](#testing-changes)
  - [Release process](#release-process)
- [License](#license)

## Command Reference

| Command | Description |
|---------|-------------|
| `ait setup` | Install/update dependencies and configure Claude Code permissions |
| `ait install` | Update aitasks to latest or specific version |
| `ait create` | Create a new task (interactive or batch mode) |
| `ait ls` | List and filter tasks by priority, effort, status, labels |
| `ait update` | Update task metadata (status, priority, labels, etc.) |
| `ait board` | Open the kanban-style TUI board |
| `ait stats` | Show task completion statistics |
| `ait clear-old` | Archive old completed task and plan files |
| `ait issue-import` | Import tasks from GitHub/GitLab issues |
| `ait issue-update` | Update or close linked GitHub/GitLab issues |
| `ait changelog` | Gather changelog data from commits and archived plans |

### Usage Examples

```bash
ait setup                               # Install dependencies
ait create                              # Interactive task creation
ait create --batch --name "fix_bug"     # Batch mode
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

### ait setup

Cross-platform dependency installer and configuration tool. This is typically the first command to run after installing aitasks.

```bash
ait setup
```

**Guided setup flow:**

1. **OS detection** — Automatically detects: macOS, Arch Linux, Debian/Ubuntu, Fedora/RHEL, WSL
2. **CLI tools** — Installs missing tools (`fzf`, `gh`, `jq`, `git`) via the platform's package manager (pacman, apt, dnf, brew). On macOS, also installs bash 5.x and coreutils
3. **Python venv** — Creates virtual environment at `~/.aitask/venv/` and installs `textual`, `pyyaml`, `linkify-it-py`
4. **Global shim** — Installs `ait` shim at `~/.local/bin/ait` that finds the nearest project-local `ait` dispatcher by walking up the directory tree. Warns if `~/.local/bin` is not in PATH
5. **Claude Code permissions** — Shows the recommended permission entries, then prompts Y/n to install them into `.claude/settings.local.json`. If settings already exist, merges permissions (union of allow-lists)
6. **Version check** — Compares local version against latest GitHub release and suggests update if newer

#### Claude Code Permissions

When you run `ait setup`, it offers to install default Claude Code permissions into `.claude/settings.local.json`. These permissions allow aitask skills to execute common operations (file listing, git commands, aiscript invocations) without prompting for manual approval each time.

The default permissions are defined in `seed/claude_settings.local.json` and stored at `aitasks/metadata/claude_settings.seed.json` during installation. If a `.claude/settings.local.json` already exists, the setup merges permissions (union of both allow-lists, preserving any existing entries). You can decline the permissions prompt and configure them manually later.

Re-run `ait setup` at any time to add the default permissions if you skipped them initially.

---

### ait install

Update the aitasks framework to a new version.

```bash
ait install                    # Update to latest release
ait install latest             # Same as above
ait install 0.2.1              # Install specific version
```

**How it works:**

1. Resolves the target version (queries GitHub API for latest, or validates the provided version number)
2. Checks if already up to date (skips if versions match)
3. Downloads `install.sh` from the target version's git tag
4. Runs the installer with `--force`, which shows the changelog between current and target versions and asks for confirmation
5. Performs the full installation (tarball download, skill installation, setup)
6. Clears the update check cache

**Automatic update check:**

The `ait` dispatcher checks for new versions once per day (at most). When a newer version is available, it shows a brief notice suggesting `ait install latest`. The check runs in the background to avoid adding latency. It is skipped for `help`, `version`, `install`, and `setup` commands.

---

### ait create

Create new task files with YAML frontmatter metadata. Supports standalone and parent/child task hierarchies.

**Interactive mode** (default — requires fzf):

1. **Parent selection** — Choose "None - create standalone task" or select an existing task as parent from a fzf list of all tasks (shown with status/priority/effort metadata)
2. **Priority** — Select via fzf: high, medium, low
3. **Effort** — Select via fzf: low, medium, high
4. **Issue type** — Select via fzf from `aitasks/metadata/task_types.txt` (bug, documentation, feature, refactor)
5. **Status** — Select via fzf: Ready, Editing, Implementing, Postponed
6. **Labels** — Iterative loop: pick from existing labels in `aitasks/metadata/labels.txt`, add a new label (auto-sanitized to lowercase alphanumeric + hyphens/underscores), or finish. New labels are persisted to the labels file for future use
7. **Dependencies** — fzf multi-select from all open tasks. For child tasks, sibling tasks appear at the top of the list. Select "None" or press Enter with nothing selected to skip
8. **Sibling dependency** (child tasks only, when child number > 1) — Prompted whether to depend on the previous sibling (e.g., t10_1). Defaults to suggesting "Yes"
9. **Task name** — Free text entry, auto-sanitized: lowercase, spaces to underscores, special chars removed, max 60 characters
10. **Description** — Iterative loop: enter text blocks, optionally add file references (fzf file walker with preview of first 50 lines, can also remove previously added references), then choose "Add more description" or "Done - create task"
11. **Post-creation** — Choose: "Show created task" (prints file contents), "Open in editor" ($EDITOR), or "Done"
12. **Git commit** — Prompted Y/n to commit the task file

**Batch mode** (for automation and scripting):

```bash
ait create --batch --name "fix_login_bug" --desc "Fix the login issue"
ait create --batch --parent 10 --name "subtask" --desc "First subtask" --commit
echo "Long description" | ait create --batch --name "my_task" --desc-file -
```

| Option | Description |
|--------|-------------|
| `--batch` | Enable batch mode (non-interactive) |
| `--name, -n NAME` | Task name (required, auto-sanitized) |
| `--desc, -d DESC` | Task description text |
| `--desc-file FILE` | Read description from file (use `-` for stdin) |
| `--priority, -p LEVEL` | high, medium, low (default: medium) |
| `--effort, -e LEVEL` | low, medium, high (default: medium) |
| `--type, -t TYPE` | Issue type from task_types.txt (default: feature) |
| `--status, -s STATUS` | Ready, Editing, Implementing, Postponed (default: Ready) |
| `--labels, -l LABELS` | Comma-separated labels |
| `--deps DEPS` | Comma-separated dependency task numbers |
| `--parent, -P NUM` | Create as child of parent task number |
| `--no-sibling-dep` | Don't auto-add dependency on previous sibling |
| `--assigned-to, -a EMAIL` | Assignee email |
| `--issue URL` | Linked issue tracker URL |
| `--commit` | Auto-commit to git |
| `--silent` | Output only filename (for scripting) |

**Key features:**
- Auto-determines next task number from active, archived, and compressed (`old.tar.gz`) tasks
- Child tasks stored in `aitasks/t<parent>/` with naming `t<parent>_<child>_<name>.md`
- Updates parent's `children_to_implement` list when creating child tasks
- Name sanitization: lowercase, underscores, no special characters, max 60 chars

---

### ait ls

List and filter tasks sorted by priority, effort, and blocked status.

```bash
ait ls -v 15                    # Top 15 tasks, verbose
ait ls -v -l ui,backend 10     # Filter by labels
ait ls -v -s all --tree 99     # Tree view, all statuses
ait ls -v --children 10 99     # List children of task t10
```

| Option | Description |
|--------|-------------|
| `[NUMBER]` | Limit output to top N tasks |
| `-v` | Verbose: show status, priority, effort, assigned, issue |
| `-s, --status STATUS` | Filter by status: Ready (default), Editing, Implementing, Postponed, Done, all |
| `-l, --labels LABELS` | Filter by labels (comma-separated, matches any) |
| `-c, --children PARENT` | List only children of specified parent task number |
| `--all-levels` | Show all tasks including children (flat list) |
| `--tree` | Hierarchical tree view with children indented under parents |

**Sort order** (unblocked tasks first, then): priority (high > medium > low) → effort (low > medium > high).

**View modes:**
- **Normal** (default) — Parent tasks only. Parents with pending children show "Has children" status
- **Children** (`--children N`) — Only child tasks of parent N
- **All levels** (`--all-levels`) — Flat list of all parents and children
- **Tree** (`--tree`) — Parents with children indented using `└─` prefix

**Metadata format:** Supports both YAML frontmatter (primary) and legacy single-line format (`--- priority:high effort:low depends:1,4`).

---

### ait update

Update task metadata fields interactively or in batch mode. Supports parent and child tasks.

**Interactive mode** (default — requires fzf):

1. **Task selection** — If no task number argument given, select from fzf list of all tasks (shown with metadata). Can also pass task number directly: `ait update 25`
2. **Field selection loop** — fzf menu showing all editable fields with current values:
   - `priority [current: medium]`
   - `effort [current: low]`
   - `status [current: Ready]`
   - `issue_type [current: feature]`
   - `dependencies [current: None]`
   - `labels [current: ui,backend]`
   - `description [edit in editor]`
   - `rename [change filename]`
   - `Done - save changes`
   - `Exit - discard changes`
3. **Per-field editing:**
   - **priority/effort/status/issue_type** — fzf selection from valid values
   - **dependencies** — fzf multi-select from all tasks (excluding current), with "Clear all dependencies" option
   - **labels** — Iterative fzf loop: select existing label, add new label (sanitized), clear all, or done
   - **description** — Shows current text, then offers "Open in editor" ($EDITOR with GUI editor support for VS Code, Sublime, etc.) or "Skip"
   - **rename** — Text entry for new name (sanitized), displays preview of new filename
4. **Save** — Select "Done" to write changes. "Exit" discards all changes
5. **Git commit** — Prompted Y/n to commit

**Batch mode** (for automation):

```bash
ait update --batch 25 --priority high --status Implementing
ait update --batch 25 --add-label "urgent" --remove-label "low-priority"
ait update --batch 25 --name "new_task_name" --commit
ait update --batch 10_1 --status Done           # Update child task
ait update --batch 10 --remove-child t10_1      # Remove child from parent
```

| Option | Description |
|--------|-------------|
| `--batch` | Enable batch mode |
| `--priority, -p LEVEL` | high, medium, low |
| `--effort, -e LEVEL` | low, medium, high |
| `--status, -s STATUS` | Ready, Editing, Implementing, Postponed, Done |
| `--type TYPE` | Issue type from task_types.txt |
| `--deps DEPS` | Dependencies (comma-separated, replaces all) |
| `--labels, -l LABELS` | Labels (comma-separated, replaces all) |
| `--add-label LABEL` | Add a single label (repeatable) |
| `--remove-label LABEL` | Remove a single label (repeatable) |
| `--description, -d DESC` | Replace description text |
| `--desc-file FILE` | Read description from file (use `-` for stdin) |
| `--name, -n NAME` | Rename task (changes filename) |
| `--assigned-to, -a EMAIL` | Assignee email (use `""` to clear) |
| `--issue URL` | Issue tracker URL (use `""` to clear) |
| `--add-child CHILD_ID` | Add child to `children_to_implement` |
| `--remove-child CHILD_ID` | Remove child from `children_to_implement` |
| `--children CHILDREN` | Set all children (replaces list) |
| `--boardcol COL` | Board column ID |
| `--boardidx IDX` | Board sort index |
| `--commit` | Auto-commit to git |
| `--silent` | Output only filename |

**Key features:**
- Auto-updates `updated_at` timestamp on every write
- Child task format: use `10_1` or `t10_1` to target child tasks
- When a child task is set to Done, automatically removes it from parent's `children_to_implement` and warns when all children are complete
- Parent tasks cannot be set to Done while `children_to_implement` is non-empty

---

### ait board

Open the kanban-style TUI board for visual task management.

```bash
ait board
```

Launches a Python-based terminal UI (built with [Textual](https://textual.textualize.io/)) that displays tasks in a kanban-style column layout. All arguments are forwarded to the Python board application.

**Requirements:**
- Python venv at `~/.aitask/venv/` with packages: `textual`, `pyyaml`, `linkify-it-py`
- Falls back to system `python3` if venv not found (warns about missing packages)
- Checks terminal capabilities and warns on legacy terminals (e.g., WSL default console)

---

### ait stats

Display task completion statistics and trends.

```bash
ait stats                  # Basic stats (last 7 days)
ait stats -d 14            # Extended daily view
ait stats -v               # Verbose with task IDs
ait stats --csv            # Export to CSV
ait stats -w sun           # Week starts on Sunday
```

| Option | Description |
|--------|-------------|
| `-d, --days N` | Show daily breakdown for last N days (default: 7) |
| `-w, --week-start DAY` | First day of week: mon, sun, tue, etc. (default: Monday) |
| `-v, --verbose` | Show individual task IDs in daily breakdown |
| `--csv [FILE]` | Export raw data to CSV (default: aitask_stats.csv) |

**Statistics provided:**

1. **Summary** — Total completions, 7-day and 30-day counts
2. **Daily breakdown** — Completions per day (with task IDs in verbose mode)
3. **Day of week averages** — This week counts + 30-day and all-time averages per weekday
4. **Label weekly trends** — Per-label completions for last 4 weeks
5. **Label day-of-week** — Per-label averages by day of week (last 30 days)
6. **Task type trends** — Parent/child and issue type (feature/bug/refactor) weekly trends
7. **Label + type trends** — Issue types by label, weekly for last 4 weeks

**Data sources:** Scans archived parent tasks (`aitasks/archived/t*_*.md`), archived child tasks (`aitasks/archived/t*/`), and compressed archives (`old.tar.gz`). Uses `completed_at` field, falling back to `updated_at` for tasks with `status: Done`.

**CSV export format:** `date, day_of_week, week_offset, task_id, labels, issue_type, task_type`. Open in LibreOffice Calc for custom charts and pivot tables.

---

### ait clear-old

Archive old completed task and plan files to compressed tar.gz archives.

```bash
ait clear-old                  # Archive and commit
ait clear-old --dry-run        # Preview what would be archived
ait clear-old --no-commit      # Archive without git commit
ait clear-old -v               # Verbose output
```

| Option | Description |
|--------|-------------|
| `-n, --dry-run` | Preview what would be archived without making changes |
| `--no-commit` | Archive files but don't commit to git |
| `-v, --verbose` | Show detailed progress (files added/removed) |

**How it works:**

1. Scans `aitasks/archived/` and `aiplans/archived/` for parent and child files
2. Keeps the most recent parent file and most recent child (per parent) uncompressed — this preserves task numbering for `ait create`
3. Archives all older files to `old.tar.gz` in each directory, preserving subdirectory structure
4. Verifies archive integrity before deleting originals
5. If `old.tar.gz` already exists, appends new files to it
6. If an existing archive is corrupted, creates a backup before starting fresh
7. Removes empty child directories after archiving
8. Commits changes to git (unless `--no-commit`)

---

### ait issue-import

Import GitHub issues as AI task files. Supports interactive selection with fzf or batch automation.

**Interactive mode** (default — requires fzf and gh CLI):

1. **Import mode selection** — Choose via fzf: "Specific issue number", "Fetch open issues and choose", "Issue number range", "All open issues"
2. **Issue selection** — Depends on mode:
   - *Specific issue*: enter issue number manually
   - *Fetch & choose*: fetches all open issues via `gh issue list`, presents in fzf with multi-select (Tab to select multiple) and preview pane showing issue body/labels
   - *Range*: enter start and end issue numbers
   - *All open*: fetches all open issues with confirmation prompt showing count
3. **Duplicate check** — Searches active and archived tasks for matching issue URL. If found, warns and offers Skip/Import anyway
4. **Issue preview** — Shows title and first 30 lines of body (truncated warning if longer). Confirm Import/Skip via fzf
5. **Task name** — Auto-generated from issue title (lowercase, sanitized). Editable with free text entry
6. **Labels** — Two-phase: first review each GitHub label individually (keep/skip via fzf), then iterative add loop (select from existing labels in `labels.txt`, add new label, or done)
7. **Priority** — fzf selection: high, medium, low
8. **Effort** — fzf selection: low, medium, high
9. **Issue type** — Auto-detected from GitHub labels: `bug` → bug, `refactor`/`tech-debt`/`cleanup` → refactor, otherwise → feature
10. **Create & commit** — Creates task file via `aitask_create.sh`, then prompts Y/n to commit to git

**Batch mode** (for automation and scripting):

```bash
ait issue-import --batch --issue 42
ait issue-import --batch --range 1-10 --priority high
ait issue-import --batch --all --skip-duplicates
ait issue-import --batch --all --parent 53 --skip-duplicates
```

| Option | Description |
|--------|-------------|
| `--batch` | Enable batch mode (required for non-interactive) |
| `--issue, -i NUM` | Import a specific issue number |
| `--range START-END` | Import issues in a number range (e.g., 5-10) |
| `--all` | Import all open issues |
| `--source, -S PLATFORM` | Source platform: github (default) |
| `--priority, -p LEVEL` | Override priority: high, medium (default), low |
| `--effort, -e LEVEL` | Override effort: low, medium (default), high |
| `--type, -t TYPE` | Override issue type (default: auto-detect from labels) |
| `--status, -s STATUS` | Override status (default: Ready) |
| `--labels, -l LABELS` | Override labels (default: mapped from issue labels) |
| `--deps DEPS` | Set dependencies (comma-separated task numbers) |
| `--parent, -P NUM` | Create as child of parent task |
| `--no-sibling-dep` | Don't add dependency on previous sibling |
| `--commit` | Auto git commit after creation |
| `--silent` | Output only created filename(s) |
| `--skip-duplicates` | Skip already-imported issues silently |
| `--no-comments` | Don't include issue comments in task description |

**Key features:**
- Platform-extensible dispatcher architecture (GitHub backend implemented; add new platforms by implementing backend functions)
- GitHub label → aitask label mapping (lowercase, special chars sanitized)
- Auto issue type detection from GitHub labels (`bug`, `refactor`, `tech-debt`, `cleanup`)
- Duplicate detection across active and archived task directories
- Issue comments included in task description by default (disable with `--no-comments`)
- Issue timestamps (created/updated) embedded in task description

---

### ait issue-update

Post implementation notes and commit references to a GitHub issue linked to a task. Optionally closes the issue. No interactive mode — fully CLI-driven.

```bash
ait issue-update 83                           # Post comment on linked issue
ait issue-update --close 53_1                 # Close issue with implementation notes
ait issue-update --commits "abc123,def456" 83 # Override commit detection
ait issue-update --dry-run 53_6               # Preview without posting
ait issue-update --close --no-comment 83      # Close silently
```

| Option | Description |
|--------|-------------|
| `TASK_NUM` | Task number (required): `53`, `53_6`, or `t53_6` |
| `--source, -S PLATFORM` | Source platform: github (default) |
| `--commits RANGE` | Override auto-detected commits. Formats: comma-separated (`abc,def`), range (`abc..def`), or single hash |
| `--close` | Close the issue after posting the comment |
| `--comment-only` | Post comment only, don't close (default behavior) |
| `--no-comment` | Close without posting a comment (requires `--close`) |
| `--dry-run` | Show what would be done without doing it |

**How it works:**

1. Reads the `issue` field from the task file's YAML frontmatter to find the GitHub issue URL
2. Resolves the archived plan file and extracts the "Final Implementation Notes" section
3. Auto-detects associated commits by searching git log for `(t<task_id>)` in commit messages (only source code commits use this parenthesized pattern)
4. Builds a markdown comment with: task reference header, link to plan file, implementation notes, and commit list
5. Posts the comment and/or closes the issue

**Key features:**
- Commit auto-detection from `(tNN)` pattern in commit messages — distinguishes source code commits from administrative ones
- Commit override with flexible formats: comma-separated hashes, hash range, or single hash
- Plan file resolution across active and archived directories
- Dry-run mode for previewing the comment before posting
- Platform-extensible dispatcher (same architecture as issue-import)

---

### ait changelog

Gather changelog data from git commits and archived task plans. Used by the `/aitask-changelog` skill to generate CHANGELOG.md entries. No interactive mode — output-oriented data gatherer.

```bash
ait changelog --gather                        # Gather all task data since last release
ait changelog --gather --from-tag v0.1.1      # Gather from a specific tag
ait changelog --check-version 0.2.0           # Check if changelog has entry for v0.2.0
```

| Option | Description |
|--------|-------------|
| `--gather` | Output structured data for all tasks since last release tag |
| `--check-version VERSION` | Check if CHANGELOG.md has a `## vVERSION` section (exit 0 if found, 1 if not) |
| `--from-tag TAG` | Override the base tag (default: auto-detect latest semver tag) |

**Output format** for `--gather`:

```
BASE_TAG: v0.1.2

=== TASK t89 ===
ISSUE_TYPE: feature
TITLE: detect capable terminal on windows
PLAN_FILE: aiplans/archived/p89_detect_capable_terminal_on_windows.md
NOTES:
- **Actual work done:** ...
COMMITS:
1c7aac4 Add terminal capability detection (t89)
=== END ===
```

Each task section includes: issue type (from task frontmatter), human-readable title (from filename), plan file path, "Final Implementation Notes" extracted from the plan, and associated commits.

**Key features:**
- Semver tag detection (`v*` tags, sorted by version)
- Task ID extraction from parenthesized `(tNN)` and `(tNN_MM)` patterns in commit messages
- Plan file resolution via shared `task_utils.sh` (checks active and archived directories)
- `--check-version` used by `create_new_release.sh` to verify changelog completeness before release
- Falls back to showing raw commits when no task-tagged commits are found

## Claude Code Integration

aitasks provides Claude Code skills that automate the full task workflow:

| Skill | Description |
|-------|-------------|
| `/aitask-pick` | The central skill — select and implement the next task (planning, branching, implementation, archival) |
| `/aitask-create` | Create tasks interactively via Claude Code |
| `/aitask-create2` | Create tasks using terminal fzf (faster alternative) |
| `/aitask-stats` | View completion statistics |
| `/aitask-cleanold` | Archive old completed files |
| `/aitask-changelog` | Generate changelog entries from commits and plans |

### /aitask-pick [number]

The central skill of the aitasks framework and the core of the development workflow. This is a full development workflow skill that manages the complete task lifecycle from selection through implementation, review, and archival.

**Usage:**
```
/aitask-pick            # Interactive task selection from prioritized list
/aitask-pick 10         # Directly select parent task t10
/aitask-pick 10_2       # Directly select child task t10_2
```

**Workflow overview:**

1. **Profile selection** — Loads an execution profile from `aitasks/metadata/profiles/` to pre-answer workflow questions and reduce prompts. See the [Execution Profiles](#execution-profiles) section below for configuration details
2. **Task selection** — Shows a prioritized list of tasks (sorted by priority, effort, blocked status) with pagination, or jumps directly to a task when a number argument is provided
3. **Child task handling** — When a parent task with children is selected, drills down to show child subtasks. Gathers context from archived sibling plan files so each child task benefits from previous siblings' implementation experience
4. **Status checks** — Detects edge cases: tasks marked Done but not yet archived, and orphaned parent tasks where all children are complete. Offers to archive them directly
5. **Assignment** — Tracks who is working on the task via email, sets status to "Implementing", commits and pushes the status change
6. **Environment setup** — Optionally creates a separate git branch and worktree (`aiwork/<task_name>/`) for isolated implementation, or works directly on the current branch
7. **Planning** — Enters Claude Code plan mode to explore the codebase and create an implementation plan. If a plan already exists, offers three options: use as-is, verify against current code, or create from scratch. Complex tasks can be decomposed into child subtasks during this phase
8. **Implementation** — Follows the approved plan, updating the plan file with progress and any deviations
9. **User review** — Presents a change summary for review. Supports an iterative "need more changes" loop where each round of feedback is logged in the plan file before re-presenting for approval
10. **Post-implementation** — Archives task and plan files, updates parent task metadata for child tasks, optionally updates/closes linked GitHub issues, and merges the branch if a worktree was used

**Key capabilities:**

- **Direct task selection** — `/aitask-pick 10` selects a parent task; `/aitask-pick 10_2` selects a specific child task. Both formats skip the interactive selection step and show a brief summary for confirmation (skippable via profile)
- **Task decomposition** — During planning, if a task is assessed as high complexity, offers to break it into child subtasks. Each child task is created with detailed context (key files, reference patterns, implementation steps, verification) so it can be executed independently in a fresh context
- **Plan mode integration** — Uses Claude Code's built-in plan mode for codebase exploration and plan design. When an existing plan file is found, offers: "Use current plan" (skip planning), "Verify plan" (check against current code), or "Create from scratch". Plan approval via ExitPlanMode is always required
- **Review cycle** — After implementation, the user reviews changes before any commit. The "Need more changes" option creates numbered change request entries in the plan file, then loops back to review. Each iteration is tracked with timestamps
- **Issue update integration** — When archiving a task that has a linked `issue` field, offers to update the GitHub issue: close with implementation notes, comment only, close silently, or skip. Uses `ait issue-update` which auto-detects associated commits and extracts plan notes
- **Abort handling** — Available at multiple checkpoints (after planning, after implementation). Reverts task status, optionally deletes the plan file, cleans up worktree/branch if created, and commits the status change
- **Branch/worktree support** — Optionally creates an isolated git worktree at `aiwork/<task_name>/` on a new `aitask/<task_name>` branch. After implementation, merges back to the base branch and cleans up the worktree and branch

#### Execution Profiles

The `/aitask-pick` skill asks several interactive questions before reaching implementation (email, local/remote, worktree, plan handling, etc.). Execution profiles let you pre-configure answers to these questions so you can go from task selection to implementation with minimal input.

Profiles are YAML files stored in `aitasks/metadata/profiles/`. Two profiles ship by default:

- **default** — All questions asked normally (empty profile, serves as template)
- **fast** — Skip confirmations, use first stored email, work locally on current branch, reuse existing plans

When you run `/aitask-pick`, the profile is selected first (Step 0a). If only one profile exists, it's auto-loaded. With multiple profiles, you're prompted to choose.

##### Profile Settings

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

##### Creating a Custom Profile

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

### /aitask-create

Create a new task file with automatic numbering and proper metadata via Claude Code prompts.

**Usage:**
```
/aitask-create
```

**Workflow:** Claude Code guides you through task creation using `AskUserQuestion` prompts:

1. **Parent selection** — Choose standalone or child of existing task
2. **Task number** — Auto-determined from active, archived, and compressed tasks
3. **Metadata** — Priority, effort, dependencies (with sibling dependency prompt for child tasks)
4. **Task name** — Free text with auto-sanitization
5. **Definition** — Iterative content collection with file reference insertion via Glob search
6. **Create & commit** — Writes task file with YAML frontmatter and commits to git

This is the Claude Code-native alternative — metadata collection happens through Claude's UI rather than terminal fzf. Use `/aitask-create2` for a faster terminal-native experience.

### /aitask-create2

Create a new task file using the terminal-native fzf interface — a faster alternative to `/aitask-create`.

**Usage:**
```
/aitask-create2
```

Launches `./aiscripts/aitask_create.sh` directly in the terminal. All prompts use fzf for fast, keyboard-driven selection:

- Parent task selection with fzf
- Priority, effort, issue type, status via fzf menus
- Labels with iterative fzf selection (existing + new)
- Dependencies via fzf multi-select with sibling tasks listed first
- Task name with auto-sanitization
- Description entry with fzf file walker for inserting file references (includes preview)
- Post-creation: view, edit in $EDITOR, or finish
- Optional git commit

**Batch mode** (for automation by AI agents):

```bash
./aiscripts/aitask_create.sh --batch --parent 10 --name "subtask" --desc "Description"
./aiscripts/aitask_create.sh --batch --parent 10 --name "parallel" --desc "Work" --no-sibling-dep
```

Preferred when speed matters — fzf selections are faster than Claude Code's `AskUserQuestion` prompts.

### /aitask-stats

View task completion statistics via Claude Code.

**Usage:**
```
/aitask-stats
```

Runs `./aiscripts/aitask_stats.sh` and displays the results. Provides the same 7 types of statistics as `ait stats`:

- Summary counts (7-day, 30-day, all-time)
- Daily breakdown with optional task IDs
- Day-of-week averages
- Per-label weekly trends (4 weeks)
- Label day-of-week breakdown (30 days)
- Task type weekly trends
- Label + issue type trends

Supports all command-line options (`-d`, `-v`, `--csv`, `-w`). For CSV export, provides guidance on opening the file in LibreOffice Calc with pivot tables and charts.

### /aitask-cleanold

Archive old completed task and plan files to compressed tar.gz archives.

**Usage:**
```
/aitask-cleanold
```

Runs `./aiscripts/aitask_clear_old.sh` to archive old files from `aitasks/archived/` and `aiplans/archived/`.

**Features:**
- Archives old files to `old.tar.gz`, keeping the most recent uncompressed (for task numbering)
- Supports parent and child task/plan hierarchies
- Verifies archive integrity before deleting originals
- Dry-run mode (`--dry-run`) for previewing
- Auto-commits to git

Supports options: `--dry-run`, `--no-commit`, `--verbose`.

### /aitask-changelog

Generate a changelog entry by analyzing commits and archived plans since the last release. Orchestrates the `ait changelog` command with AI-powered summarization.

**Usage:**
```
/aitask-changelog
```

**Workflow:**

1. **Gather release data** — Runs `ait changelog --gather` to collect all tasks since the last release tag, with their issue types, plan files, commits, and implementation notes
2. **Summarize plans** — Reads each task's archived plan file and generates concise user-facing summaries (what changed from the user's perspective, not internal details)
3. **Draft changelog entry** — Groups summaries by issue type under `### Features`, `### Bug Fixes`, `### Improvements` headings. Format: `- **Task name** (tNN): summary`
4. **Version number** — Reads `VERSION` file, calculates next patch/minor, asks user to select or enter custom version
5. **Version validation** — Ensures the selected version is strictly greater than the latest version in CHANGELOG.md (semver comparison)
6. **Overlap detection** — Checks if any gathered tasks already appear in the latest changelog section. If overlap found, offers: "New tasks only", "Replace latest section", or "Abort"
7. **Review and finalize** — Shows the complete formatted entry for approval. Options: "Write to CHANGELOG.md", "Edit entry", or "Abort"
8. **Write and commit** — Inserts the entry into CHANGELOG.md (after the `# Changelog` header) and commits

**Key features:**
- User-facing summaries: focuses on what changed, not implementation details
- Version validation prevents duplicate or regressive version numbers
- Overlap detection handles incremental changelog updates when some tasks were already documented
- Supports both new CHANGELOG.md creation and insertion into existing files

## Task File Format
Tasks are markdown files with YAML frontmatter in the `aitasks/` directory:
Task files use the naming convention `t<number>_<name>.md
Executed task files are stored in aitasks/archived and their associated plan files in aiplans/archived

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
documentation
feature
refactor
```

To add a custom type, simply add a new line to the file. All scripts (`ait create`, `ait update`, `ait board`, `ait stats`) read from this file dynamically.

## Development

### Architecture

The framework follows a dispatcher pattern. The `ait` script in the project root routes subcommands to individual scripts:

```
ait <subcommand> [args]  →  aiscripts/aitask_<subcommand>.sh [args]
```

**Directory layout:**

| Directory | Purpose |
|-----------|---------|
| `aiscripts/` | All framework scripts (`aitask_*.sh`) |
| `aiscripts/lib/` | Shared library scripts sourced by main scripts |
| `.claude/skills/aitask-*` | Claude Code skill definitions (SKILL.md files) |
| `aitasks/` | Active task files (`t<N>_name.md`) and child task directories (`t<N>/`) |
| `aiplans/` | Active plan files (`p<N>_name.md`) and child plan directories (`p<N>/`) |
| `aitasks/archived/` | Completed task files and child directories |
| `aiplans/archived/` | Completed plan files and child directories |
| `aitasks/metadata/` | Configuration: `labels.txt`, `task_types.txt`, `emails.txt`, `profiles/` |

### Library Scripts

Shared utilities in `aiscripts/lib/` are sourced by main scripts. Both libraries use a double-source guard (`[[ -n "${_VAR_LOADED:-}" ]] && return 0`) to prevent duplicate loading.

#### lib/task_utils.sh

Task and plan file resolution utilities. Sources `terminal_compat.sh` automatically.

**Directory variables** (override before sourcing if needed):

- `TASK_DIR` — Active task directory (default: `aitasks`)
- `ARCHIVED_DIR` — Archived task directory (default: `aitasks/archived`)
- `PLAN_DIR` — Active plan directory (default: `aiplans`)
- `ARCHIVED_PLAN_DIR` — Archived plan directory (default: `aiplans/archived`)

**Functions:**

- **`resolve_task_file(task_id)`** — Find a task file by number (e.g., `"53"` or `"53_6"`). Searches active directory first, then archived. Dies if not found or if multiple matches exist.
- **`resolve_plan_file(task_id)`** — Find the corresponding plan file using `t→p` prefix conversion (e.g., `t53_name.md` → `p53_name.md`). Returns empty string if not found.
- **`extract_issue_url(file_path)`** — Parse the `issue:` field from a task file's YAML frontmatter. Returns empty string if not present.
- **`extract_final_implementation_notes(plan_path)`** — Extract the `## Final Implementation Notes` section from a plan file. Stops at the next `##` heading. Trims leading/trailing blank lines.

#### lib/terminal_compat.sh

Terminal capability detection and colored output helpers.

**Color variables:** `RED`, `GREEN`, `YELLOW`, `BLUE`, `NC` (no color) — standard ANSI escape codes.

**Logging functions:**

- **`die(message)`** — Print red error message to stderr and exit 1
- **`info(message)`** — Print blue informational message
- **`success(message)`** — Print green success message
- **`warn(message)`** — Print yellow warning to stderr

**Detection functions:**

- **`ait_check_terminal_capable()`** — Returns 0 if the terminal supports modern features (TUI, true color). Checks `COLORTERM`, `WT_SESSION`, `TERM_PROGRAM`, `TERM`, and tmux/screen presence. Caches result in `AIT_TERMINAL_CAPABLE`.
- **`ait_is_wsl()`** — Returns 0 if running under Windows Subsystem for Linux (checks `/proc/version` for "microsoft").
- **`ait_warn_if_incapable_terminal()`** — Prints suggestions for upgrading to a modern terminal if capability check fails. Provides WSL-specific guidance when applicable. Suppressed by `AIT_SKIP_TERMINAL_CHECK=1`.

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

1. Run `/aitask-changelog` in Claude Code to generate the changelog entry for the new version
2. Run `./create_new_release.sh` which bumps the `VERSION` file, creates a git tag, and pushes to trigger the GitHub Actions release workflow

## License
This project is licensed under the MIT License with the Commons Clause condition.

What this means:
✅ You can: Use, copy, and modify the code for free.

✅ You can: Use aitasks as a library to power your own commercial products or SaaS applications.

❌ You cannot: Sell aitasks itself, or a derivative version of it, as a standalone product or service (e.g., selling a "Pro" version of the library or a managed aitasks hosting service) without prior written consent.

For the full legal text, please see the LICENSE file.
See [LICENSE](LICENSE) for details.
