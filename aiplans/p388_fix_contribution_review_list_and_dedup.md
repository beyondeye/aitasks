---
Task: t388_fix_contribution_review_list_and_dedup.md
Worktree: (current branch)
Branch: (current branch)
Base branch: main
---

## Context

The `/aitask-contribution-review` skill has two bugs:
1. When invoked without an `<issue_number>`, Claude improvises with `gh issue list` — a GitHub-specific command that breaks on GitLab/Bitbucket.
2. No guard against re-importing issues already imported as tasks.

## Plan

### Part A: Add `list-issues` subcommand to `aitask_contribution_review.sh`

**File:** `.aitask-scripts/aitask_contribution_review.sh`

1. Add `list-issues` to the case statement in `parse_args()` (line ~104):
   ```bash
   fetch|find-related|fetch-multi|post-comment|list-issues|check-imported)
   ```

2. No argument validation needed for `list-issues` (no issue number required).

3. Add `cmd_list_issues()` function (after `cmd_post_comment`, before MAIN):
   ```bash
   cmd_list_issues() {
       local issues_json
       issues_json=$(source_list_contribution_issues) || die "Failed to list contribution issues"
       local count
       count=$(echo "$issues_json" | jq 'length')
       if [[ "$count" -eq 0 ]]; then
           echo "NO_ISSUES"
           return
       fi
       for ((i = 0; i < count; i++)); do
           local num title body author
           num=$(echo "$issues_json" | jq -r ".[$i].number")
           title=$(echo "$issues_json" | jq -r ".[$i].title")
           body=$(echo "$issues_json" | jq -r ".[$i].body // \"\"")
           author=$(echo "$issues_json" | jq -r ".[$i].author // .[$i].labels[0].name // \"unknown\"")
           # Check for contribute metadata
           parse_contribute_metadata "$body"
           local has_meta="false"
           [[ -n "${CONTRIBUTE_FINGERPRINT_VERSION:-}" ]] && has_meta="true"
           echo "@@@ISSUE:${num}@@@"
           echo "TITLE:${title}"
           echo "HAS_METADATA:${has_meta}"
       done
   }
   ```

   Note: The author field is tricky — `source_list_contribution_issues()` JSON doesn't include author for GitHub (gh issue list --json doesn't include it by default in the contribution_check backends). We'll simplify to just num, title, has_metadata — these are sufficient for the SKILL.md selection UI.

4. Add routing in `main()` case statement (line ~510):
   ```bash
   list-issues) cmd_list_issues ;;
   check-imported) cmd_check_imported "$REVIEW_ISSUE" ;;
   ```

5. Update `show_help()` to document both new subcommands.

### Part B: Add `check-imported` subcommand to `aitask_contribution_review.sh`

**File:** `.aitask-scripts/aitask_contribution_review.sh`

1. Add `cmd_check_imported()` function that replicates `check_duplicate_import()` from `aitask_issue_import.sh:479-489`:
   ```bash
   cmd_check_imported() {
       local issue_num="$1"
       local found=""
       found=$(grep -rl "^issue:.*/$issue_num$" "$TASK_DIR"/ 2>/dev/null | head -1)
       if [[ -z "$found" ]]; then
           found=$(grep -rl "^issue:.*/$issue_num$" "$ARCHIVED_DIR"/ 2>/dev/null | head -1)
       fi
       if [[ -n "$found" ]]; then
           echo "IMPORTED:${found}"
       else
           echo "NOT_IMPORTED"
       fi
   }
   ```

2. Add `check-imported` to the argument validation case — requires an issue number (same as `fetch`).

### Part C: Update SKILL.md — no-argument handling

**File:** `.claude/skills/aitask-contribution-review/SKILL.md`

Add a "Step 0: Resolve Issue Number" before Step 1:

- If `<issue_number>` argument is provided, use it directly and proceed to Step 1.
- If no argument provided:
  1. Run `./.aitask-scripts/aitask_contribution_review.sh list-issues`
  2. Parse output: `@@@ISSUE:<num>@@@` / `TITLE:<title>` / `HAS_METADATA:<bool>` blocks
  3. If `NO_ISSUES`: inform user "No open contribution issues found." and abort
  4. Filter to only issues with `HAS_METADATA:true` (contribution issues)
  5. Present via `AskUserQuestion` (issue `#<num>` as label, title as description)
  6. Use selected issue number for Step 1

### Part D: Update SKILL.md — duplicate import guard

**File:** `.claude/skills/aitask-contribution-review/SKILL.md`

Add "Step 1b: Check for Duplicate Import" after Step 1:

1. Run `./.aitask-scripts/aitask_contribution_review.sh check-imported <issue_number>`
2. If `IMPORTED:<path>`:
   - Extract task name from path
   - Use `AskUserQuestion`: "Issue #N has already been imported as task <task_name> (<path>). How to proceed?"
   - Options: "Proceed anyway" / "Abort"
   - If abort, end workflow

## Files to Modify

1. `.aitask-scripts/aitask_contribution_review.sh` — Parts A + B (add `list-issues` and `check-imported`)
2. `.claude/skills/aitask-contribution-review/SKILL.md` — Parts C + D (no-arg handling + dedup guard)

### Part E: Automated Tests

**File:** `tests/test_contribution_review.sh` (append to existing file, before the Summary section)

Add tests following the existing patterns in this file (assert_eq, assert_contains, mock functions via temp files).

#### Tests for `list-issues` subcommand

**Test 20: Argument parsing — list-issues accepts no issue number:**
```bash
REVIEW_SUBCMD="" REVIEW_ISSUE="" ...
parse_args list-issues --platform github
assert_eq "Subcommand parsed" "list-issues" "$REVIEW_SUBCMD"
assert_eq "No issue needed for list-issues" "" "$REVIEW_ISSUE"
```

**Test 21: cmd_list_issues with mocked source_list_contribution_issues (multiple issues):**
Mock `source_list_contribution_issues` to return JSON with 2 issues (one with metadata, one without). Mock `parse_contribute_metadata` to set/clear `CONTRIBUTE_FINGERPRINT_VERSION`. Verify output contains `@@@ISSUE:<num>@@@`, `TITLE:`, and correct `HAS_METADATA` values.

**Test 22: cmd_list_issues — empty result:**
Mock `source_list_contribution_issues` to return `[]`. Verify output is `NO_ISSUES`.

#### Tests for `check-imported` subcommand

**Test 23: Argument parsing — check-imported requires issue number:**
```bash
result=$(parse_args check-imported 2>&1 || true)
assert_contains "Error for missing issue" "requires an issue number" "$result"
```

**Test 24: Argument parsing — check-imported parses issue number:**
```bash
parse_args check-imported 42 --platform github
assert_eq "Subcommand parsed" "check-imported" "$REVIEW_SUBCMD"
assert_eq "Issue parsed" "42" "$REVIEW_ISSUE"
```

**Test 25: cmd_check_imported — finds imported task:**
Create a temp directory with a mock task file containing `issue: https://github.com/owner/repo/issues/42`. Set `TASK_DIR` to the temp dir. Run `cmd_check_imported 42`. Assert output contains `IMPORTED:`.

**Test 26: cmd_check_imported — NOT_IMPORTED for unknown issue:**
Same temp setup. Run `cmd_check_imported 99999`. Assert output is `NOT_IMPORTED`.

**Test 27: cmd_check_imported — finds in archived dir:**
Create a task file in the `ARCHIVED_DIR` temp dir with matching `issue:` frontmatter. Run `cmd_check_imported`. Assert output contains `IMPORTED:` pointing to the archived file.

#### Tests for help output

**Test 28: Help output includes list-issues and check-imported:**
```bash
output=$("$PROJECT_DIR/.aitask-scripts/aitask_contribution_review.sh" --help 2>&1)
assert_contains "Help shows list-issues" "list-issues" "$output"
assert_contains "Help shows check-imported" "check-imported" "$output"
```

## Verification

1. Run existing tests to confirm no regressions:
   ```bash
   bash tests/test_contribution_review.sh
   ```

2. Run shellcheck:
   ```bash
   shellcheck .aitask-scripts/aitask_contribution_review.sh
   ```

3. Manual: verify SKILL.md reads correctly and covers both new flows

## Final Implementation Notes
- **Actual work done:** Implemented all 4 parts (A-D) plus Part E (automated tests) as planned
- **Deviations from plan:** Removed the `author` field from `cmd_list_issues()` output (plan noted it was tricky, opted to simplify). Also made `check-imported` skip `setup_platform()` since it's local-only (grep on task files)
- **Issues encountered:** None — clean implementation
- **Key decisions:** `check-imported` returns early before `setup_platform()` in `main()` since it doesn't need network access. The `list-issues` subcommand reuses `parse_contribute_metadata()` per-issue to check for metadata presence
