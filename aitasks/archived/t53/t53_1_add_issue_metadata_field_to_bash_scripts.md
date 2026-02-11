---
priority: high
effort: medium
depends: []
issue_type: feature
status: Done
labels: [scripting, aitasks]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-02-10 16:16
updated_at: 2026-02-10 16:27
completed_at: 2026-02-10 16:27
---

## Context

This is child task 1 of t53 (import GitHub issues as tasks). The parent task adds the ability to import GitHub issues as aitask files. This child task adds the foundation: a new `issue` metadata field to the three bash task management scripts. The field stores a full URL to the issue page (e.g., `https://github.com/owner/repo/issues/123`), making it platform-agnostic for future GitLab/Bitbucket support.

The existing bash scripts (`aitask_update.sh`, `aitask_create.sh`, `aitask_ls.sh`) explicitly enumerate known frontmatter fields. Unknown fields are **dropped** when `aitask_update.sh` rewrites task files. This means the `issue` field must be added as a known field to all three scripts.

## Key Files to Modify

1. **`aitask_update.sh`** - Most complex changes. The `write_task_file()` function takes positional parameters and only writes known fields. Need to:
   - Add `BATCH_ISSUE` and `BATCH_ISSUE_SET` batch mode variables (near line 44, after `BATCH_BOARDIDX_SET`)
   - Add `CURRENT_ISSUE` parsing variable (near line 58, after `CURRENT_BOARDIDX`)
   - Add `--issue` argument parsing in the CLI args section (near line 182, after `--boardidx`)
   - Add `issue)` case in `parse_yaml_frontmatter()` (near line 313, after `boardidx`)
   - Reset `CURRENT_ISSUE=""` at start of parsing (near line 255)
   - Add `issue` as 14th positional parameter to `write_task_file()` function
   - Write `issue:` field in output BETWEEN `assigned_to` and `created_at` (only if non-empty)
   - **Update ALL 4 call sites** of `write_task_file()` to pass the new 14th parameter:
     - Line ~589: `handle_child_task_completion()` parent rewrite
     - Line ~592: `handle_child_task_completion()` child rewrite
     - Line ~1032: `run_interactive_mode()`
     - Line ~1189: `run_batch_mode()`
   - Save/restore `CURRENT_ISSUE` in `handle_child_task_completion()` alongside other saved variables
   - Add `has_update` check: `[[ "$BATCH_ISSUE_SET" == true ]] && has_update=true`
   - Compute `new_issue` in batch mode: default to `CURRENT_ISSUE`, override if `BATCH_ISSUE_SET`
   - Add issue display to interactive summary
   - Update help text

2. **`aitask_create.sh`** - Add `--issue URL` support for batch mode:
   - Add `BATCH_ISSUE=""` variable (near line 34, after `BATCH_ASSIGNED_TO`)
   - Add `--issue) BATCH_ISSUE="$2"; shift 2 ;;` in argument parsing (near line 113)
   - Add `issue` as new parameter to `create_task_file()` and `create_child_task_file()`
   - Write `issue:` in YAML output (between `assigned_to` and `created_at`, only if non-empty)
   - Pass `"$BATCH_ISSUE"` in batch mode call sites
   - Update help text

3. **`aitask_ls.sh`** - Add `issue` to verbose display:
   - Add `issue_text=""` variable (near line 166)
   - Add `issue)` case to `parse_yaml_frontmatter()` (near line 233)
   - Reset in `parse_task_metadata()` (near line 314)
   - Append to verbose output string (near line 388): `Issue: <url>` if present

## Reference Files for Patterns

- `aitask_update.sh`: Look at how `boardcol`/`boardidx` were added as optional fields - `issue` follows the same pattern (optional, only written if non-empty)
- `aitask_update.sh`: Look at how `assigned_to` is handled - same "write only if non-empty" pattern
- `aitask_create.sh`: Look at how `--assigned-to` is handled for the pattern to follow with `--issue`

## Verification Steps

1. Create a test task with issue field:
   ```bash
   ./aitask_create.sh --batch --name "test_issue_field" --desc "Test" --issue "https://github.com/test/repo/issues/1"
   ```
2. Verify the field appears in the created file
3. Update the task and verify the field is preserved:
   ```bash
   ./aitask_update.sh --batch <N> --priority high
   ```
4. Verify `issue` field still present after update
5. Update the issue field itself:
   ```bash
   ./aitask_update.sh --batch <N> --issue "https://github.com/test/repo/issues/2"
   ```
6. Verify in `aitask_ls.sh -v` output
7. Clean up test task
