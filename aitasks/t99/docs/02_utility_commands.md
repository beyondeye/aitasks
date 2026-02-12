<!-- SECTION: Command Reference — Utility Commands -->
<!-- PLACEMENT: after "### ait update" in Command Reference -->

### ait setup

Cross-platform dependency installer and configuration tool.

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

<!-- SECTION: Claude Code Integration — Utility Skills -->
<!-- PLACEMENT: after /aitask-create2 in Claude Code Integration -->

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
