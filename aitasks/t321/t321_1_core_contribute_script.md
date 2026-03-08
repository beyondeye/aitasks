---
priority: medium
effort: high
depends: []
issue_type: feature
status: Implementing
labels: [auto-update]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-03-08 09:31
updated_at: 2026-03-08 15:59
---

## Context

This is child task 1 of t321 (aitask-contribute skill). It creates the core bash script that handles upstream diff generation, contributor resolution, and GitHub issue creation. The script is batch-only (no interactive mode, no `ait` dispatcher entry) — all user interaction goes through the aitask-contribute skill (t321_3).

The aitask-contribute feature enables users to contribute their local modifications to the aitasks framework back to the upstream `beyondeye/aitasks` repo by opening structured GitHub issues.

## Key Files to Create

- `.aitask-scripts/aitask_contribute.sh` (~400-500 lines)

## Reference Files for Patterns

- `.aitask-scripts/aitask_issue_import.sh` — script structure pattern (header, helpers, parse_args, show_help)
- `.aitask-scripts/lib/repo_fetch.sh` — reuse `repo_fetch_file()` for fetching upstream file content
- `.aitask-scripts/lib/terminal_compat.sh` — `die()`, `warn()`, `info()`
- `.aitask-scripts/lib/task_utils.sh` — general utilities
- `.aitask-scripts/aitask_pr_import.sh` — reference for contributor email resolution pattern

## Implementation Plan

### Core Functions to Implement

**1. Mode detection (`detect_contribute_mode`):**
- Check if current repo is a clone/fork of `beyondeye/aitasks` by parsing git remote URL for `beyondeye/aitasks`
- Returns `clone` or `downstream` to stdout

**2. Area resolution:**
- Predefined area → directory mappings:
  - `scripts` → `.aitask-scripts/`
  - `claude-skills` → `.claude/skills/`
  - `gemini` → `.gemini/skills/`, `.gemini/commands/`
  - `codex` → `.agents/skills/`
  - `opencode` → `.opencode/skills/`, `.opencode/commands/`
  - `website` → `website/` (clone mode only)
  - Custom path via `--area-path`
- `--list-areas` flag: outputs available areas for the detected mode (one per line: `area_name|dir1,dir2|description`)

**3. Changed file discovery (`list_changed_files`):**
- **Clone mode:** `git diff --name-only main -- <area_paths>`
- **Downstream mode:** Walk files in area directories, fetch each from upstream via `repo_fetch_file()`, compare with `diff -q`. Output files that differ.
- `--list-changes --area <name>` flag: outputs changed file paths (one per line)

**4. Diff generation (`generate_diff`):**
- **Clone mode:** `git diff main -- <files>` — produces unified diff
- **Downstream mode:** For each file: fetch upstream content via `repo_fetch_file()`, then `diff -u <(echo "$upstream_content") "$local_file"` — produces unified diff per file
- Output: concatenated unified diffs with file path headers

**5. Issue body generation (`build_issue_body`):**
- Produces structured markdown with sections: Contribution title, Contributor info, Version, Scope, Merge approach, Motivation, Changed Files table, Code Changes with diffs
- Diffs included as fenced `diff` code blocks
- **Large diff strategy:** For diffs >50 lines per file: show first 50 lines in rendered code block with note "*Preview — full diff available in raw view of this issue*", include complete diff in HTML comment (`<!-- full-diff:filename ... -->`)
- Embed contributor metadata as HTML comment: `<!-- aitask-contribute-metadata contributor: username contributor_email: email based_on_version: X.Y.Z -->`

**6. Issue creation (`create_issue`):**
- `gh issue create -R beyondeye/aitasks --title "<title>" --body "$issue_body" --label "contribution"`
- Returns issue URL on stdout

**7. Contributor resolution (`resolve_contributor`):**
- `gh api user` for GitHub username/ID, construct noreply email (`{id}+{username}@users.noreply.github.com`)
- Fallback: `git config user.name`/`git config user.email`

### CLI Flags (batch-only)

- `--area <name>` — contribution area
- `--area-path <path>` — custom area path
- `--files <file1,file2,...>` — specific files to include
- `--title <text>` — contribution title
- `--motivation <text>` — motivation text
- `--scope <type>` — bug_fix|enhancement|new_feature|documentation|other
- `--merge-approach <text>` — proposed merge approach
- `--dry-run` — generate issue body to stdout, don't create issue
- `--silent` — output only issue URL
- `--repo <owner/repo>` — override upstream repo (default: `beyondeye/aitasks`)
- `--list-areas` — output available areas for current mode
- `--list-changes --area <name>` — output changed files in area
- `--diff-preview-lines <N>` — lines shown in rendered preview per file (default: 50)

### Script Structure

```bash
#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/lib/terminal_compat.sh"
source "$SCRIPT_DIR/lib/task_utils.sh"
source "$SCRIPT_DIR/lib/repo_fetch.sh"

DEFAULT_UPSTREAM_REPO="beyondeye/aitasks"
DEFAULT_DIFF_PREVIEW_LINES=50

# --- Area definitions ---
# --- Helper functions ---
# --- Core functions (mode detection, area resolution, diff, issue body, create) ---
# --- Argument parsing ---
# --- Main ---
```

## Verification Steps

- `shellcheck .aitask-scripts/aitask_contribute.sh` passes
- `./.aitask-scripts/aitask_contribute.sh --list-areas` outputs area names
- `./.aitask-scripts/aitask_contribute.sh --dry-run --area scripts --files ".aitask-scripts/aitask_ls.sh" --title "Test" --motivation "Testing" --scope enhancement --merge-approach "clean merge"` generates structured output
- All portability conventions followed (no GNU-only sed/grep, `#!/usr/bin/env bash`)
