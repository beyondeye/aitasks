---
Task: t53_3_create_aitask_import_batch_mode.md
Parent Task: aitasks/t53_import_gh_issue_as_task.md
Sibling Tasks: aitasks/t53/t53_2_*.md, aitasks/t53/t53_4_*.md, aitasks/t53/t53_5_*.md
Archived Sibling Plans: aiplans/archived/p53/p53_*_*.md
Branch: main
Base branch: main
---

# Plan: Create aitask_import.sh batch mode (t53_3)

## Context

This task creates the `aitask_import.sh` script that imports GitHub issues as task files. It uses the `gh` CLI to fetch issue data and `aitask_create.sh --batch` to create tasks. The batch mode supports importing a single issue, a range, or all open issues.

The sibling task t53_1 already added `--issue URL` support to `aitask_create.sh`, so we can pass issue URLs when creating tasks.

## Key Files

- **`aitask_import.sh`** (NEW) — Main import script
- **`aitask_create.sh`** — Reference for structure, called to create tasks

## Implementation

### Step 1: Script skeleton with helpers

Create `aitask_import.sh` with:
- Shebang `#!/bin/bash`, `set -e`
- Color definitions and helpers (`die`, `info`, `success`, `warn`) — copy from `aitask_create.sh` lines 12-50
- `sanitize_name()` — copy from `aitask_create.sh` lines 608-612
- Global batch mode variables with defaults

### Step 2: Argument parsing

Implement `parse_args()` and `show_help()` supporting these flags:

```
--batch                  Enable batch mode (required)
--source, -S PLATFORM    Source platform: github (default)
--issue, -i NUM          Import a specific issue number
--range START-END        Import issues in a number range (e.g., 5-10)
--all                    Import all open issues
--priority, -p LEVEL     Override priority (default: medium)
--effort, -e LEVEL       Override effort (default: medium)
--type, -t TYPE          Override issue type (default: auto-detect from labels)
--status, -s STATUS      Override status (default: Ready)
--labels, -l LABELS      Override labels (default: from issue labels)
--deps DEPS              Set dependencies
--parent, -P NUM         Create as child of parent task
--no-sibling-dep         Don't add dependency on previous sibling
--commit                 Auto git commit after creation
--silent                 Output only created filename(s)
--skip-duplicates        Skip already-imported issues silently
--help, -h               Show help
```

### Step 3: GitHub backend functions

```bash
github_check_cli()       # Verify gh + jq installed
github_fetch_issue()     # gh issue view NUM --json title,body,labels,url
github_list_issues()     # gh issue list --state open --limit 500 --json number,title,labels,url
github_map_labels()      # Extract label names, lowercase, sanitize for aitask labels
github_detect_type()     # Return "bug" if "bug" label found, else "feature"
github_preview_issue()   # gh issue view NUM (human-readable, for future interactive mode)
```

### Step 4: Dispatcher layer

Source-dispatching functions (`source_check_cli`, `source_fetch_issue`, etc.) with `case "$SOURCE"` for platform abstraction. Comment with `# PLATFORM-EXTENSION-POINT`.

### Step 5: Duplicate detection

```bash
check_duplicate_import() {
    local issue_num="$1"
    # Search active and archived tasks for matching issue URL
    grep -rl "^issue:.*/$issue_num$" aitasks/ 2>/dev/null | head -1
}
```

### Step 6: Core import function — `import_single_issue()`

1. Check for duplicates (skip or warn based on `--skip-duplicates`)
2. Fetch issue JSON via `source_fetch_issue`
3. Extract title, body, url, labels from JSON with `jq`
4. Determine task name via `sanitize_name "$title"`
5. Determine labels (use `--labels` override or `source_map_labels`)
6. Determine issue_type (use `--type` override or `source_detect_type`)
7. Build description: `"## $title\n\n$body"`
8. Call `./aitask_create.sh --batch` with all args, piping description via `--desc-file -`

### Step 7: Batch mode dispatch — `run_batch_mode()`

1. `source_check_cli` — validate tools
2. Dispatch based on `--issue`, `--range`, or `--all`:
   - Single issue: call `import_single_issue`
   - Range: loop from start to end
   - All: fetch issue list, extract numbers, loop
3. Error if none of the three is specified

### Step 8: Make executable

`chmod +x aitask_import.sh`

## Verification

1. Test single issue import: `./aitask_import.sh --batch --issue 2`
2. Verify task file has correct title, description, labels, issue URL
3. Test duplicate detection (run same import again)
4. Test with overrides: `./aitask_import.sh --batch --issue 2 --priority high --labels "custom" --skip-duplicates`
5. Test `--all` mode: `./aitask_import.sh --batch --all --silent --skip-duplicates`
6. Clean up test tasks

## Final Implementation Notes
- **Actual work done:** Implemented exactly as planned. Created `aitask_import.sh` (370 lines) with batch mode supporting single issue (`--issue`), range (`--range`), and all open issues (`--all`). Platform abstraction layer with GitHub backend using `gh` CLI + `jq`. Duplicate detection across active and archived tasks. All flags passed through to `aitask_create.sh --batch`.
- **Deviations from plan:** Fixed `set -e` compatibility issues — `((count++))` evaluates to 0 (false) when count is 0, replaced with `count=$((count + 1))`. Also changed `[[ ... != true ]] && cmd` pattern to `[[ ... == true ]] || cmd` to avoid short-circuit exit with `set -e`.
- **Issues encountered:** Bash `set -e` strict mode interacts poorly with arithmetic increment `((count++))` when count starts at 0, and with `[[ cond ]] && action` when cond is false. Both are common bash gotchas.
- **Key decisions:** Used `$SCRIPT_DIR` to resolve `aitask_create.sh` path so the script works from any working directory. `BATCH_TYPE` defaults to empty string (auto-detect from labels) rather than "feature".
- **Notes for sibling tasks:**
  - The import script delegates to `aitask_create.sh --batch --desc-file -` for actual task creation, piping the description via stdin
  - `github_preview_issue()` is implemented but unused in batch mode — ready for t53_4 (interactive mode)
  - `github_list_issues()` and all dispatcher functions are available for t53_4 to reuse
  - The `--source` flag defaults to "github" with PLATFORM-EXTENSION-POINT comments for future backends
  - Interactive mode placeholder returns error: "Interactive mode not yet implemented"

## Post-Implementation

Follow Step 9 of aitask-pick workflow for archival and commit.
