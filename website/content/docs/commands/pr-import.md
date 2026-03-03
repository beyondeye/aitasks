---
title: "PR Import"
linkTitle: "PR Import"
weight: 42
description: "ait pr-import — import pull requests as tasks or extract PR data for AI analysis"
---

## ait pr-import

Import GitHub/GitLab/Bitbucket pull requests as AI task files, or extract structured PR data for use with the [`/aitask-pr-review`](../../skills/aitask-pr-review/) skill. Supports interactive selection with fzf or batch automation. The source platform is auto-detected from the git remote URL (`github.com` → GitHub, `gitlab.com` → GitLab, `bitbucket.org` → Bitbucket). Use `--source` to override.

**Interactive mode** (default — requires fzf and gh/glab/bkt CLI):

1. **Import mode selection** — Choose via fzf: "Specific PR number", "Fetch open PRs and choose", "PR number range", "All open PRs"
2. **PR selection** — Depends on mode:
   - *Specific PR*: enter PR number manually
   - *Fetch & choose*: fetches all open PRs via `gh pr list` (or `glab mr list` for GitLab, `bkt pr list` for Bitbucket), presents in fzf with multi-select (Tab to select multiple) and preview pane showing PR details
   - *Range*: enter start and end PR numbers
   - *All open*: fetches all open PRs
3. **PR preview** — Shows title, author, branch info, and first 30 lines of description (truncated warning if longer). Choose: "Import as task (basic)", "Extract PR data only (for /aitask-pr-review skill)", or "Skip"
4. **Task metadata** — Edit task name (auto-generated from PR title), review/keep/add labels, select priority/effort. Issue type is auto-detected from PR labels
5. **Create & commit** — Creates task file via `ait create`, then prompts to commit to git

**Batch mode** (for automation and scripting):

```bash
ait pr-import --batch --pr 42                         # Import single PR as task
ait pr-import --batch --pr 42 --data-only --silent    # Extract data only (for skill)
ait pr-import --batch --all --skip-duplicates         # Import all open PRs
ait pr-import --batch --range 5-10 --priority high    # Import range with metadata
ait pr-import --batch --list --silent                 # List open PRs (machine-parseable)
ait pr-import --batch --pr 42 --no-diff --no-reviews  # Import without diff (faster)
```

| Option | Description |
|--------|-------------|
| `--batch` | Enable batch mode (required for non-interactive) |
| `--pr NUM` | PR/MR number to import |
| `--range START-END` | Import PRs in a number range (e.g., 5-10) |
| `--all` | Import all open PRs |
| `--list` | List open PRs (tab-separated output for skill parsing) |
| `--source, -S PLATFORM` | Source platform: `github`, `gitlab`, `bitbucket` (auto-detected from git remote) |
| `--repo OWNER/REPO` | GitLab/Bitbucket repo override for cross-repo imports |
| `--data-only` | Write intermediate data file only, don't create task |
| `--priority, -p LEVEL` | Override priority: `high`, `medium` (default), `low` |
| `--effort, -e LEVEL` | Override effort: `low`, `medium` (default), `high` |
| `--type, -t TYPE` | Override issue type (default: auto-detect from PR labels) |
| `--status, -s STATUS` | Override status (default: `Ready`) |
| `--labels, -l LABELS` | Override labels (default: mapped from PR labels) |
| `--deps DEPS` | Set dependencies (comma-separated task numbers) |
| `--parent, -P NUM` | Create as child of parent task |
| `--no-sibling-dep` | Don't add automatic dependency on previous sibling |
| `--commit` | Auto git commit after creation |
| `--silent` | Output only created filename(s); suppress status messages |
| `--skip-duplicates` | Skip already-imported PRs silently |
| `--no-comments` | Don't include PR comments in intermediate data |
| `--no-diff` | Skip diff extraction entirely |
| `--no-reviews` | Skip review comment extraction |
| `--max-diff-lines N` | Truncate diff at N lines (default: 5000) |

**Key features:**
- Multi-platform support: GitHub (`gh`), GitLab (`glab`), and Bitbucket Cloud (`bkt`) backends with auto-detection from git remote URL
- Duplicate detection across active and archived task directories (matches by PR URL pattern)
- Contributor email resolution for attribution (GitHub noreply, GitLab noreply, or Bitbucket email)
- Intermediate data format for AI-powered analysis via [`/aitask-pr-review`](../../skills/aitask-pr-review/)
- PR metadata stored in task frontmatter: `pull_request` (URL), `contributor` (username), `contributor_email`
- PR label → aitask label mapping (lowercase, special chars sanitized)
- Auto issue type detection from PR labels (`bug`, `refactor`, `tech-debt`, `cleanup`)

**Intermediate data format** (`--data-only`):

Files are written to `.aitask-pr-data/<num>.md` with YAML frontmatter containing PR metadata (`pr_number`, `pr_url`, `contributor`, `contributor_email`, `platform`, `title`, `state`, `base_branch`, `head_branch`, `additions`, `deletions`, `changed_files`, `fetched_at`) and markdown sections for description, comments, reviews, inline review comments, changed file list, and diff (truncated at `--max-diff-lines`).
