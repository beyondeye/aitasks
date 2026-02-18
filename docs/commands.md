# Command Reference

## Table of Contents

- [Usage Examples](#usage-examples)
- [ait setup](#ait-setup)
  - [Claude Code Permissions](#claude-code-permissions)
- [ait install](#ait-install)
- [ait create](#ait-create)
- [ait ls](#ait-ls)
- [ait update](#ait-update)
- [ait board](#ait-board)
- [ait stats](#ait-stats)
- [ait zip-old](#ait-zip-old)
- [ait issue-import](#ait-issue-import)
- [ait issue-update](#ait-issue-update)
- [ait changelog](#ait-changelog)

---

| Command | Description |
|---------|-------------|
| `ait setup` | Install/update dependencies and configure Claude Code permissions |
| `ait install` | Update aitasks to latest or specific version |
| `ait create` | Create a new task as draft, or finalize drafts (interactive or batch mode) |
| `ait ls` | List and filter tasks by priority, effort, status, labels |
| `ait update` | Update task metadata (status, priority, labels, etc.) |
| `ait board` | Open the kanban-style TUI board |
| `ait stats` | Show task completion statistics |
| `ait zip-old` | Archive old completed task and plan files |
| `ait issue-import` | Import tasks from GitHub/GitLab issues |
| `ait issue-update` | Update or close linked GitHub/GitLab issues |
| `ait changelog` | Gather changelog data from commits and archived plans |

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

## ait setup

Cross-platform dependency installer and configuration tool. This is typically the first command to run after installing aitasks.

```bash
ait setup
```

**Auto-bootstrap:** When run via the global shim (`~/.local/bin/ait`) in a directory without an existing aitasks installation, `ait setup` automatically downloads and installs the latest release before running the setup flow. This lets you bootstrap new projects with a single command — no need to run the `curl | bash` installer separately.

**Guided setup flow:**

1. **OS detection** — Automatically detects: macOS, Arch Linux, Debian/Ubuntu, Fedora/RHEL, WSL
2. **CLI tools** — Installs missing tools (`fzf`, `gh`, `jq`, `git`) via the platform's package manager (pacman, apt, dnf, brew). On macOS, also installs bash 5.x and coreutils
3. **Git repo** — Checks for an existing git repository; offers to initialize one and commit framework files if not found
4. **Draft directory** — Creates `aitasks/new/` for local draft tasks and adds it to `.gitignore` so drafts stay local-only
5. **Task ID counter** — Initializes the `aitask-ids` counter branch on the remote for atomic task numbering. This prevents duplicate task IDs when multiple PCs create tasks against the same repo
6. **Python venv** — Creates virtual environment at `~/.aitask/venv/` and installs `textual`, `pyyaml`, `linkify-it-py`
7. **Global shim** — Installs `ait` shim at `~/.local/bin/ait` that finds the nearest project-local `ait` dispatcher by walking up the directory tree. Warns if `~/.local/bin` is not in PATH
8. **Claude Code permissions** — Shows the recommended permission entries, then prompts Y/n to install them into `.claude/settings.local.json`. If settings already exist, merges permissions (union of allow-lists)
9. **Version check** — Compares local version against latest GitHub release and suggests update if newer

### Claude Code Permissions

When you run `ait setup`, it offers to install default Claude Code permissions into `.claude/settings.local.json`. These permissions allow aitask skills to execute common operations (file listing, git commands, aiscript invocations) without prompting for manual approval each time.

The default permissions are defined in `seed/claude_settings.local.json` and stored at `aitasks/metadata/claude_settings.seed.json` during installation. If a `.claude/settings.local.json` already exists, the setup merges permissions (union of both allow-lists, preserving any existing entries). You can decline the permissions prompt and configure them manually later.

Re-run `ait setup` at any time to add the default permissions if you skipped them initially.

---

## ait install

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

## ait create

Create new task files with YAML frontmatter metadata. Supports standalone and parent/child task hierarchies.

**Interactive mode** (default — requires fzf):

0. **Draft management** — If drafts exist in `aitasks/new/`, a menu appears: select a draft to continue editing, finalize (assign real ID and commit), or delete — or create a new task
1. **Parent selection** — Choose "None - create standalone task" or select an existing task as parent from a fzf list of all tasks (shown with status/priority/effort metadata)
2. **Priority** — Select via fzf: high, medium, low
3. **Effort** — Select via fzf: low, medium, high
4. **Issue type** — Select via fzf from `aitasks/metadata/task_types.txt` (bug, chore, documentation, feature, performance, refactor, style, test)
5. **Status** — Select via fzf: Ready, Editing, Implementing, Postponed
6. **Labels** — Iterative loop: pick from existing labels in `aitasks/metadata/labels.txt`, add a new label (auto-sanitized to lowercase alphanumeric + hyphens/underscores), or finish. New labels are persisted to the labels file for future use
7. **Dependencies** — fzf multi-select from all open tasks. For child tasks, sibling tasks appear at the top of the list. Select "None" or press Enter with nothing selected to skip
8. **Sibling dependency** (child tasks only, when child number > 1) — Prompted whether to depend on the previous sibling (e.g., t10_1). Defaults to suggesting "Yes"
9. **Task name** — Free text entry, auto-sanitized: lowercase, spaces to underscores, special chars removed, max 60 characters. Preview shows `draft_*_<name>.md` (real ID is assigned during finalization)
10. **Description** — Iterative loop: enter text blocks, optionally add file references (fzf file walker with preview of first 50 lines, can also remove previously added references), then choose "Add more description" or "Done - create task"
11. **Post-creation** — Choose: "Finalize now" (claim real ID and commit), "Show draft", "Open in editor" ($EDITOR), or "Save as draft" (finalize later via `ait create` or `--batch --finalize`)

**Batch mode** (for automation and scripting):

```bash
# Creates draft in aitasks/new/ (no network needed)
ait create --batch --name "fix_login_bug" --desc "Fix the login issue"

# Auto-finalize: claim real ID and commit immediately (requires network)
ait create --batch --name "add_feature" --desc "New feature" --commit

# Finalize a specific draft
ait create --batch --finalize draft_20260213_1423_fix_login.md

# Finalize all pending drafts
ait create --batch --finalize-all

# Child task (auto-finalized with --commit)
ait create --batch --parent 10 --name "subtask" --desc "First subtask" --commit

# Read description from stdin
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
| `--commit` | Claim real ID and commit to git immediately (auto-finalize) |
| `--finalize FILE` | Finalize a specific draft from `aitasks/new/` (claim ID, move to `aitasks/`, commit) |
| `--finalize-all` | Finalize all pending drafts in `aitasks/new/` |
| `--silent` | Output only filename (for scripting) |

**Key features:**
- Tasks are created as **drafts** in `aitasks/new/` by default (no network required). Finalization claims a globally unique ID from an atomic counter on the `aitask-ids` git branch
- Drafts use timestamp-based filenames (`draft_YYYYMMDD_HHMM_<name>.md`) and are local-only (gitignored)
- Child task IDs are assigned via local scan (safe because the parent's unique ID acts as a namespace)
- Atomic counter fallback: in interactive mode, warns and asks for consent to use local scan; in batch mode, fails hard if counter is unavailable
- Child tasks stored in `aitasks/t<parent>/` with naming `t<parent>_<child>_<name>.md`
- Updates parent's `children_to_implement` list when creating child tasks
- Name sanitization: lowercase, underscores, no special characters, max 60 chars
- Duplicate ID detection: `ait ls` warns if duplicate task IDs are found; `ait update` fails with a suggestion to run `ait setup`

---

## ait ls

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

## ait update

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

## ait board

Open the kanban-style TUI board for visual task management.

```bash
ait board
```

Launches a Python-based terminal UI (built with [Textual](https://textual.textualize.io/)) that displays tasks in a kanban-style column layout. All arguments are forwarded to the Python board application.

For full usage documentation — including tutorials, keyboard shortcuts, how-to guides, and configuration — see the [Kanban Board documentation](board.md).

**Requirements:**
- Python venv at `~/.aitask/venv/` with packages: `textual`, `pyyaml`, `linkify-it-py`
- Falls back to system `python3` if venv not found (warns about missing packages)
- Checks terminal capabilities and warns on legacy terminals (e.g., WSL default console)

---

## ait stats

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

## ait zip-old

Archive old completed task and plan files to compressed tar.gz archives.

```bash
ait zip-old                    # Archive and commit
ait zip-old --dry-run          # Preview what would be archived
ait zip-old --no-commit        # Archive without git commit
ait zip-old -v                 # Verbose output
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

## ait issue-import

Import GitHub/GitLab issues as AI task files. Supports interactive selection with fzf or batch automation. The source platform is auto-detected from the git remote URL (`github.com` → GitHub, `gitlab.com` → GitLab). Use `--source` to override.

**Interactive mode** (default — requires fzf and gh/glab CLI):

1. **Import mode selection** — Choose via fzf: "Specific issue number", "Fetch open issues and choose", "Issue number range", "All open issues"
2. **Issue selection** — Depends on mode:
   - *Specific issue*: enter issue number manually
   - *Fetch & choose*: fetches all open issues via `gh issue list` (or `glab issue list` for GitLab), presents in fzf with multi-select (Tab to select multiple) and preview pane showing issue body/labels
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
| `--source, -S PLATFORM` | Source platform: `github`, `gitlab` (auto-detected from git remote) |
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
- Platform-extensible dispatcher architecture (GitHub and GitLab backends implemented; add new platforms by implementing backend functions)
- Auto-detection of source platform from git remote URL (override with `--source`)
- Issue label → aitask label mapping (lowercase, special chars sanitized)
- Auto issue type detection from issue labels (`bug`, `refactor`, `tech-debt`, `cleanup`)
- Duplicate detection across active and archived task directories
- Issue comments included in task description by default (disable with `--no-comments`)
- Issue timestamps (created/updated) embedded in task description

---

## ait issue-update

Post implementation notes and commit references to a GitHub/GitLab issue linked to a task. Optionally closes the issue. No interactive mode — fully CLI-driven. The source platform is auto-detected from the issue URL in the task's frontmatter. Use `--source` to override.

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
| `--source, -S PLATFORM` | Source platform: `github`, `gitlab` (auto-detected from issue URL) |
| `--commits RANGE` | Override auto-detected commits. Formats: comma-separated (`abc,def`), range (`abc..def`), or single hash |
| `--close` | Close the issue after posting the comment |
| `--comment-only` | Post comment only, don't close (default behavior) |
| `--no-comment` | Close without posting a comment (requires `--close`) |
| `--dry-run` | Show what would be done without doing it |

**How it works:**

1. Reads the `issue` field from the task file's YAML frontmatter to find the issue URL (auto-detects GitHub/GitLab from the URL)
2. Resolves the archived plan file and extracts the "Final Implementation Notes" section
3. Auto-detects associated commits by searching git log for `(t<task_id>)` in commit messages (only source code commits use this parenthesized pattern)
4. Builds a markdown comment with: task reference header, link to plan file, implementation notes, and commit list
5. Posts the comment and/or closes the issue

**Key features:**
- Commit auto-detection from `(tNN)` pattern in commit messages — distinguishes source code commits from administrative ones
- Commit override with flexible formats: comma-separated hashes, hash range, or single hash
- Plan file resolution across active and archived directories
- Dry-run mode for previewing the comment before posting
- Auto-detection of source platform from issue URL (override with `--source`)
- Platform-extensible dispatcher (same architecture as issue-import)

---

## ait changelog

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
