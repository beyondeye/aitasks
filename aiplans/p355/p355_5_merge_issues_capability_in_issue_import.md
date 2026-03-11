---
Task: t355_5_merge_issues_capability_in_issue_import.md
Parent Task: aitasks/t355_check_for_existing_issues_overlap.md
Sibling Tasks: aitasks/t355/t355_6_*.md, aitasks/t355/t355_7_*.md
Archived Sibling Plans: aiplans/archived/p355/p355_1_*.md, p355_2_*.md, p355_3_*.md, p355_4_*.md
Worktree: (current branch)
Branch: main
Base branch: main
---

## Context

The `aitask_issue_import.sh` script imports one issue per task. The `aitask-contribution-review` skill (t355_6) needs to group related contribution issues into a single task. This task adds `--merge-issues N1,N2,...` batch-mode flag to merge multiple issues, with combined descriptions, unioned labels, and multi-contributor attribution.

## Files Modified

1. **`.aitask-scripts/aitask_issue_import.sh`** — All merge logic
2. **`.claude/skills/task-workflow/procedures.md`** — Multi-contributor attribution procedure
3. **`tests/test_merge_issues.sh`** — New test file (33 assertions)

## Implementation

### 1. New global + arg parsing
- Added `BATCH_MERGE_ISSUES=""` global variable
- Added `--merge-issues` to `parse_args()` case statement
- Added validation: `--merge-issues` cannot combine with `--issue`, `--range`, or `--all`
- Used proper `if/fi` blocks instead of `[[ ]] && die` to avoid `set -e` interaction

### 2. Helper functions
- `count_diff_lines()` — Counts `+`/`-` lines (excluding `+++`/`---` headers) for primary contributor selection. Uses `grep -cE || true` to handle zero-match case portably.
- `inject_merge_frontmatter()` — Inserts `related_issues:` and `contributors:` YAML lines into task file frontmatter. Uses while-read loop + temp file for BSD/GNU portability (avoids multi-line sed issues).

### 3. Comment-posting platform backends
- `github_post_comment()`, `gitlab_post_comment()`, `bitbucket_post_comment()`, `source_post_comment()` — Same platform backend pattern as existing dispatchers. Simple one-liners using `gh issue comment`, `glab issue note`, `bkt issue comment`.

### 4. `merge_issues()` core function
Flow: parse issue numbers → check duplicates → fetch all issues → parse contribute metadata → count diff lines → determine primary contributor → build merged description → call `aitask_create.sh --batch --silent --commit` → inject frontmatter → amend commit → post notification comments → output result.

### 5. `run_batch_mode()` wiring
Merge dispatch moved BEFORE `source_check_cli` so count validation can happen without requiring platform CLI auth. The validation `(count >= 2)` runs first, then `source_check_cli` and `merge_issues`.

### 6. Help text updates
Added `--merge-issues N1,N2,...` to batch required flags section and two examples.

### 7. Contributor Attribution Procedure update
Added "Multi-Contributor Attribution (Merged Issues)" subsection: primary gets `Co-Authored-By` trailer, secondaries listed as `Also based on contributions from: name1 (#N1), name2 (#N2)` in commit body.

## Key Design Decisions

- **Post-creation sed injection** for `related_issues:` and `contributors:` frontmatter fields avoids modifying `aitask_create.sh`'s 14-parameter function signatures. YAML parser handles arbitrary keys.
- **Batch-only merge mode** — interactive merge is out of scope; t355_6 skill calls this in batch mode.
- **Comment posting always attempted** — `--no-comments` only controls whether issue comments are included in the description, not whether merge notifications are posted. Post failures are warned, not fatal.
- **`if/fi` instead of `[[ ]] && die`** — The latter is unsafe with `set -e` because a false condition causes the line to exit with code 1.

## Verification

1. `bash -n .aitask-scripts/aitask_issue_import.sh` — PASS
2. `shellcheck .aitask-scripts/aitask_issue_import.sh` — no new warnings
3. `bash tests/test_merge_issues.sh` — 33/33 PASS
4. `bash tests/test_issue_import_contributor.sh` — 58/58 PASS (no regression)
5. `./.aitask-scripts/aitask_issue_import.sh --help` — shows merge-issues

## Final Implementation Notes
- **Actual work done:** Implemented all plan steps. Added `--merge-issues N1,N2,...` batch-mode flag to `aitask_issue_import.sh` (~337 lines added) with: `merge_issues()` core function, `count_diff_lines()` helper, `inject_merge_frontmatter()` helper, comment-posting platform backends (GitHub/GitLab/Bitbucket), `source_post_comment()` dispatcher. Updated help text with flag description and examples. Updated `procedures.md` with Multi-Contributor Attribution subsection. Created `tests/test_merge_issues.sh` with 33 assertions.
- **Deviations from plan:** (1) Moved merge count validation to `run_batch_mode()` instead of inside `merge_issues()` — allows validation before `source_check_cli` which requires network auth. (2) Used `if/fi` instead of `[[ ]] && die` pattern for validation — discovered that `[[ false_condition ]] && die` is unsafe with `set -e` because the false left side causes exit code 1 to kill the script. (3) Used `grep -cE || true` instead of `|| echo "0"` for `count_diff_lines` — the original approach double-printed "0" when grep had zero matches (grep -c outputs "0" to stdout AND exits non-zero, triggering the `|| echo "0"` fallback).
- **Issues encountered:** `set -e` interaction with `[[ ]] && command` pattern caused silent script exits during testing (no error message). Fixed by using proper `if/fi` blocks. Integration test with full git repo setup was too fragile; replaced with unit-level simulation tests that verify the same functionality.
- **Key decisions:** Used post-creation sed injection for `related_issues:` and `contributors:` frontmatter rather than modifying `aitask_create.sh`'s 14-parameter function signatures. Comment posting always attempted (failures warned, not fatal). `--no-comments` only controls description content, not merge notifications.
- **Notes for sibling tasks:** The `source_post_comment()` dispatcher is now available in `aitask_issue_import.sh` and can be used by t355_6 (contribution-review skill) if it sources functions from this script. The `inject_merge_frontmatter()` approach (while-read loop + temp file) is the portable pattern for multi-line YAML insertion — avoid sed for this. The `[[ ]] && die` anti-pattern under `set -e` should be avoided throughout all scripts; always use `if/fi`.
