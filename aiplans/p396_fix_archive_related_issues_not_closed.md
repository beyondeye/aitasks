---
Task: t396_fix_archive_related_issues_not_closed.md
Worktree: (none - working on current branch)
Branch: main
Base branch: main
---

## Context

When contribution issues are merged via `aitask_issue_import.sh --merge-issues`, the resulting task has a `related_issues: ["url1", "url2"]` YAML array in frontmatter. During archival, only the primary `issue:` field is processed — all URLs in `related_issues:` are silently skipped, leaving secondary source issues open/uncommented.

## Plan

### 1. Add `extract_related_issues()` to `task_utils.sh`

**File:** `.aitask-scripts/lib/task_utils.sh` (after `extract_pr_url()`, ~line 332)

New function following the pattern of `extract_issue_url()` (lines 283-305):
- Parse YAML frontmatter for `related_issues:` field
- Handle the inline array format: `related_issues: ["url1", "url2"]`
- Output one URL per line (newline-separated) for easy `while read` consumption
- Return empty if field is missing or empty

```bash
extract_related_issues() {
    local file_path="$1"
    local in_yaml=false

    while IFS= read -r line; do
        if [[ "$line" == "---" ]]; then
            if [[ "$in_yaml" == true ]]; then break
            else in_yaml=true; continue; fi
        fi
        if [[ "$in_yaml" == true && "$line" =~ ^related_issues:[[:space:]]*(.*) ]]; then
            local raw="${BASH_REMATCH[1]}"
            # Strip brackets, split on comma, trim quotes/spaces
            raw="${raw#\[}" ; raw="${raw%\]}"
            if [[ -z "$raw" ]]; then return; fi
            while IFS=',' read -ra items; do
                for item in "${items[@]}"; do
                    item=$(echo "$item" | sed 's/^[[:space:]"]*//;s/[[:space:]"]*$//')
                    [[ -n "$item" ]] && echo "$item"
                done
            done <<< "$raw"
            return
        fi
    done < "$file_path"
}
```

### 2. Emit `RELATED_ISSUE:` lines from `aitask_archive.sh`

**File:** `.aitask-scripts/aitask_archive.sh`

Add `extract_related_issues` calls at all 4 emission locations, each emitting one `RELATED_ISSUE:<task_num>:<url>` line per URL. The prefix matches the context:

**Location A — Parent task archival (~line 214, after `ISSUE:` block):**
```bash
# Check for related issues
local related_url
while IFS= read -r related_url; do
    [[ -n "$related_url" ]] && echo "RELATED_ISSUE:$task_num:$related_url"
done < <(extract_related_issues "$task_file")
```

**Location B — Folded task (~line 315, after `FOLDED_ISSUE:` block):**
```bash
while IFS= read -r related_url; do
    [[ -n "$related_url" ]] && echo "FOLDED_RELATED_ISSUE:$folded_id:$related_url"
done < <(extract_related_issues "$folded_file")
```

**Location C — Child task archival (~line 375, after child `ISSUE:` block):**
```bash
while IFS= read -r related_url; do
    [[ -n "$related_url" ]] && echo "RELATED_ISSUE:$task_id:$related_url"
done < <(extract_related_issues "$child_task_file")
```

**Location D — Parent auto-archival (~line 427, after `PARENT_ISSUE:` block):**
```bash
while IFS= read -r related_url; do
    [[ -n "$related_url" ]] && echo "PARENT_RELATED_ISSUE:$parent_num:$related_url"
done < <(extract_related_issues "$parent_task_file")
```

### 3. Handle `RELATED_ISSUE:` in SKILL.md Step 9

**File:** `.claude/skills/task-workflow/SKILL.md` (~line 445, after `ISSUE:` handling)

Add 3 new output line handlers:

- **`RELATED_ISSUE:<task_num>:<url>`** — Execute the Issue Update Procedure (same as `ISSUE:`) but with `--issue-url` flag since the URL differs from the primary `issue:` field:
  - Use `AskUserQuestion` with same options (Close with notes / Comment only / Close silently / Skip)
  - Commands use `--issue-url "<url>"` flag (like folded issues do)

- **`PARENT_RELATED_ISSUE:<task_num>:<url>`** — Same handling as `RELATED_ISSUE:` but for parent context

- **`FOLDED_RELATED_ISSUE:<folded_task_num>:<url>`** — Same handling as `FOLDED_ISSUE:` (already uses `--issue-url`)

### 4. Update `issue-update.md` procedure

**File:** `.claude/skills/task-workflow/issue-update.md`

Add a section documenting `RELATED_ISSUE:` handling: same AskUserQuestion flow as primary issues, but uses `--issue-url` flag for the script calls since the URL comes from the output line, not from the task's `issue:` field.

### 5. Verify `inject_merge_frontmatter()` in `aitask_issue_import.sh`

**File:** `.aitask-scripts/aitask_issue_import.sh` (lines 74-112)

Already verified during exploration — the function correctly builds and injects `related_issues: ["url1", "url2"]` format. No changes needed.

## Files to Modify

1. `.aitask-scripts/lib/task_utils.sh` — Add `extract_related_issues()`
2. `.aitask-scripts/aitask_archive.sh` — Emit `RELATED_ISSUE:` / `PARENT_RELATED_ISSUE:` / `FOLDED_RELATED_ISSUE:` lines (4 locations)
3. `.claude/skills/task-workflow/SKILL.md` — Handle new output lines in Step 9
4. `.claude/skills/task-workflow/issue-update.md` — Document related issue handling
5. `tests/test_archive_related_issues.sh` — New test file (5 test cases)

### 6. Automated tests: `tests/test_archive_related_issues.sh`

**New file:** `tests/test_archive_related_issues.sh`

Following the pattern of `tests/test_archive_folded.sh` (same helpers, setup_archive_project, teardown structure).

**Test A: `extract_related_issues` unit tests**
- Source `task_utils.sh` and test the function directly against temp task files:
  - Multiple URLs: `related_issues: ["https://github.com/o/r/issues/1", "https://github.com/o/r/issues/2"]` → outputs 2 lines
  - Single URL: `related_issues: ["https://github.com/o/r/issues/1"]` → outputs 1 line
  - Empty array: `related_issues: []` → outputs nothing
  - Missing field (no `related_issues:` line) → outputs nothing

**Test B: Parent archival emits `RELATED_ISSUE:` lines**
- Create parent task with `issue:` and `related_issues:` fields
- Run `aitask_archive.sh`
- Assert output contains `ISSUE:<num>:<primary_url>`
- Assert output contains `RELATED_ISSUE:<num>:<url1>` and `RELATED_ISSUE:<num>:<url2>`

**Test C: Child archival emits `RELATED_ISSUE:` lines**
- Create parent + child task, child has `related_issues:`
- Archive child
- Assert `RELATED_ISSUE:` lines emitted for child's related issues

**Test D: Parent auto-archival (last child) emits `PARENT_RELATED_ISSUE:` lines**
- Create parent with `related_issues:` and one remaining child
- Archive last child → triggers parent auto-archive
- Assert `PARENT_RELATED_ISSUE:` lines emitted for parent's related issues

**Test E: Folded task `FOLDED_RELATED_ISSUE:` emission**
- Create task with `folded_tasks: [50]`, where t50 has `related_issues:`
- Archive the main task
- Assert `FOLDED_RELATED_ISSUE:` lines emitted for the folded task's related issues

## Verification

1. Run `bash tests/test_archive_related_issues.sh` — all tests should pass
2. Run `shellcheck .aitask-scripts/aitask_archive.sh .aitask-scripts/lib/task_utils.sh`

## Final Implementation Notes

- **Actual work done:** Implemented all 5 planned steps plus tests. Added `extract_related_issues()`, emit `RELATED_ISSUE:`/`PARENT_RELATED_ISSUE:`/`FOLDED_RELATED_ISSUE:` at all 4 archival locations, updated SKILL.md and issue-update.md, wrote 5 test cases (18 assertions).
- **Deviations from plan:** Discovered that `aitask_update.sh --remove-child` rewrites parent frontmatter and drops `related_issues:`. Fixed by caching parent issue/related/PR fields before the `--remove-child` call and emitting from cache during parent auto-archival. This also protects the existing `PARENT_ISSUE:` and `PARENT_PR:` emissions from the same bug.
- **Issues encountered:** Test D initially failed because parent related issues were read after `--remove-child` had stripped them. Resolved by caching.
- **Key decisions:** Used `--issue-url` flag for all related issue script calls (consistent with existing folded issue handling). Emitted one line per URL rather than a comma-separated list for simpler parsing.

## Step 9 (Post-Implementation)

After implementation: review, commit, archive task.
