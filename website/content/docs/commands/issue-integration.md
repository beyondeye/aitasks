---
title: "Issue Integration & Utilities"
linkTitle: "Issues & Utilities"
weight: 40
description: "ait issue-import, ait issue-update, ait changelog, and ait zip-old commands"
---

## ait issue-import

Import GitHub/GitLab/Bitbucket issues as AI task files. Supports interactive selection with fzf or batch automation. The source platform is auto-detected from the git remote URL (`github.com` → GitHub, `gitlab.com` → GitLab, `bitbucket.org` → Bitbucket). Use `--source` to override.

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
| `--source, -S PLATFORM` | Source platform: `github`, `gitlab`, `bitbucket` (auto-detected from git remote) |
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
- Platform-extensible dispatcher architecture (GitHub, GitLab, and Bitbucket backends implemented; add new platforms by implementing backend functions)
- Auto-detection of source platform from git remote URL (override with `--source`)
- Issue label → aitask label mapping (lowercase, special chars sanitized)
- Auto issue type detection from issue labels (`bug`, `refactor`, `tech-debt`, `cleanup`)
- Duplicate detection across active and archived task directories
- Issue comments included in task description by default (disable with `--no-comments`)
- Issue timestamps (created/updated) embedded in task description

---

## ait issue-update

Post implementation notes and commit references to a GitHub/GitLab/Bitbucket issue linked to a task. Optionally closes the issue. No interactive mode — fully CLI-driven. The source platform is auto-detected from the issue URL in the task's frontmatter. Use `--source` to override.

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
| `--source, -S PLATFORM` | Source platform: `github`, `gitlab`, `bitbucket` (auto-detected from issue URL) |
| `--commits RANGE` | Override auto-detected commits. Formats: comma-separated (`abc,def`), range (`abc..def`), or single hash |
| `--close` | Close the issue after posting the comment |
| `--comment-only` | Post comment only, don't close (default behavior) |
| `--no-comment` | Close without posting a comment (requires `--close`) |
| `--dry-run` | Show what would be done without doing it |

**How it works:**

1. Reads the `issue` field from the task file's YAML frontmatter to find the issue URL (auto-detects GitHub/GitLab/Bitbucket from the URL)
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
