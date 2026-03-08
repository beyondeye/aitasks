---
Task: t321_1_core_contribute_script.md
Parent Task: aitasks/t321_removeautoupdatefromdocsorimplement.md
Sibling Tasks: aitasks/t321/t321_2_*.md, aitasks/t321/t321_3_*.md, aitasks/t321/t321_4_*.md, aitasks/t321/t321_5_*.md
Worktree: (current directory)
Branch: (current branch)
Base branch: main
---

# Implementation Plan: t321_1 — Core Contribute Script

## Overview

Create `.aitask-scripts/aitask_contribute.sh` — a batch-only script that handles upstream diff generation, contributor resolution, and GitHub issue creation for the aitask-contribute skill.

## Steps

### 1. Script scaffold

Create `.aitask-scripts/aitask_contribute.sh` with standard header:

```bash
#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/lib/terminal_compat.sh"
source "$SCRIPT_DIR/lib/task_utils.sh"
source "$SCRIPT_DIR/lib/repo_fetch.sh"

DEFAULT_UPSTREAM_REPO="beyondeye/aitasks"
DEFAULT_DIFF_PREVIEW_LINES=50
VERSION_FILE="$SCRIPT_DIR/VERSION"
```

### 2. Area definitions

Define area name → directory mappings as associative arrays or case statements:

```bash
# Area definitions: name|directories|description
AREAS=(
  "scripts|.aitask-scripts/|Core scripts (shell and Python)"
  "claude-skills|.claude/skills/|Claude Code skills"
  "gemini|.gemini/skills/,.gemini/commands/|Gemini CLI skills and commands"
  "codex|.agents/skills/|Codex CLI skills"
  "opencode|.opencode/skills/,.opencode/commands/|OpenCode skills and commands"
  "website|website/|Website documentation (clone/fork mode only)"
)
```

Note: Use `declare -a` (indexed array), not `declare -A` (associative), for compatibility. Parse with IFS='|'.

### 3. Implement core functions

**`detect_contribute_mode()`** — parse git remote URL for `beyondeye/aitasks`. Output `clone` or `downstream`.

**`resolve_area_dirs(area_name)`** — look up area in AREAS array, return directory paths. Die if area is `website` and mode is `downstream`.

**`list_areas()`** — for `--list-areas` flag. Output: `MODE:<clone|downstream>` on first line, then `AREA|<name>|<dirs>|<description>` per area. Filter out `website` if mode is `downstream`.

**`list_changed_files(area, area_dirs)`** — for `--list-changes`. Clone mode: `git diff --name-only main -- <dirs>`. Downstream mode: walk files, fetch upstream via `repo_fetch_file()`, compare with `diff -q`. Handle `AITASK_CONTRIBUTE_UPSTREAM_DIR` env var override for testing.

**`generate_diff(files)`** — Clone mode: `git diff main -- <files>`. Downstream mode: per-file `diff -u` against fetched upstream. Handle `AITASK_CONTRIBUTE_UPSTREAM_DIR` override.

**`resolve_contributor()`** — try `gh api user --jq '.login,.id'`, construct noreply email. Fallback to `git config`.

**`build_issue_body(title, motivation, scope, merge_approach, files, diff_output)`** — assemble structured markdown. Split diff by file. For each file: if diff >PREVIEW_LINES, show preview + HTML comment with full diff. Embed `<!-- aitask-contribute-metadata ... -->`.

**`create_issue(title, body, repo)`** — `gh issue create -R "$repo" --title "$title" --body "$body" --label "contribution"`. Parse and output issue URL.

### 4. Argument parsing

`parse_args()` function handling all batch flags. Die with usage on invalid combinations.

### 5. Main dispatch

```bash
main() {
    parse_args "$@"
    if [[ "$LIST_AREAS" == true ]]; then
        list_areas; exit 0
    fi
    if [[ "$LIST_CHANGES" == true ]]; then
        # requires --area
        list_changed_files ...; exit 0
    fi
    # Full flow: resolve contributor, generate diff, build body, create/dry-run
}
main "$@"
```

## Key Reuse

- `lib/repo_fetch.sh` → `repo_fetch_file()` for downstream mode upstream file fetching
- `lib/terminal_compat.sh` → `die()`, `warn()`, `info()`
- GitHub noreply email pattern from `aitask_pr_import.sh` → `github_resolve_contributor_email()`

## Testing hook

Support `AITASK_CONTRIBUTE_UPSTREAM_DIR` env var: when set, `list_changed_files()` and `generate_diff()` read "upstream" files from this directory instead of calling `repo_fetch_file()`. This enables offline testing (t321_5).

## Verification

- `shellcheck .aitask-scripts/aitask_contribute.sh` passes
- `--list-areas` outputs areas
- `--list-changes --area scripts` outputs changed files (clone mode)
- `--dry-run` generates complete issue body
- No GNU-only sed/grep features used

## Step 9 Reference
Post-implementation: archive task via task-workflow Step 9.
