---
Task: t168_remove_legacy_task_metadata_format.md
Worktree: (current branch)
Branch: main
Base branch: main
---

## Context

Task t168 asks to remove legacy single-line metadata format support from aitask bash scripts. The legacy format (`--- priority:high effort:low depends:1,4`) predates the current YAML frontmatter format. All task files now use YAML frontmatter exclusively, making the legacy parsing code dead weight.

Only **one script** contains legacy format support: `aiscripts/aitask_ls.sh`.

## Changes

### `aiscripts/aitask_ls.sh`

1. **Remove help text about legacy format** (lines 32-33, 48-50):
   - Update to say only YAML format is supported
   - Delete legacy format documentation

2. **Delete `parse_legacy_format()` function** (lines 269-303):
   - Remove the entire 35-line function

3. **Simplify `parse_task_metadata()`** (lines 332-361):
   - Remove the `elif` branch for legacy format
   - Remove the `first_line` variable — no longer needed
   - Simplify: just call `parse_yaml_frontmatter "$file_path"` directly

## Verification

1. Run `./aiscripts/aitask_ls.sh -v 5` — verify normal task listing works
2. Run `./aiscripts/aitask_ls.sh -v -l bash_scripts 5` — verify label filtering works
3. Run `./aiscripts/aitask_ls.sh --tree` — verify tree view works

## Final Implementation Notes
- **Actual work done:** Removed all legacy single-line metadata format support from `aitask_ls.sh` — the only script that had it. Deleted `parse_legacy_format()` function (35 lines), simplified `parse_task_metadata()` to call `parse_yaml_frontmatter()` directly, and updated help text.
- **Deviations from plan:** None — implementation matched the plan exactly.
- **Issues encountered:** None.
- **Key decisions:** Removed the `first_line` / `head -n 1` check entirely since `parse_yaml_frontmatter()` already validates the `---` delimiter internally and returns gracefully if absent.
