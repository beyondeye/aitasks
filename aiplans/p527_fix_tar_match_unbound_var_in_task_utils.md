---
Task: t527_fix_tar_match_unbound_var_in_task_utils.md
Worktree: (current branch)
Branch: main
Base branch: main
---

# Plan for t527: Fix `tar_match` unbound variable in task_utils.sh

## Context

During archival of t521_3 on 2026-04-12, `aitask_archive.sh` aborted mid-flow with:

```
/home/ddt/Work/aitasks/.aitask-scripts/lib/task_utils.sh: line 358: tar_match: unbound variable
```

The parent task/plan files had already been moved to `archived/` but the archival commit never ran, leaving a dirty tree. Any task archival that hits the "Tier 3 numbered archives" fallback for a plan or task whose corresponding `_find_archive_for_task` lookup returns empty will trip the same bug under `set -u`.

## Root cause

`.aitask-scripts/lib/task_utils.sh` has four Tier-3-fallback blocks that all follow the same shape:

```bash
local archive_path tar_match
archive_path=$(_find_archive_for_task "$task_id" "$ARCHIVED_*")
if [[ -n "$archive_path" ]]; then
    tar_match=$(_search_archive "$archive_path" "...")
fi
if [[ -z "$tar_match" ]]; then   # <-- fails under `set -u` when the if above was skipped
    ...
fi
```

`local archive_path tar_match` declares both variables without initializing `tar_match`. When `_find_archive_for_task` returns empty, the inner `if` is skipped and `tar_match` stays unset, so the next `[[ -z "$tar_match" ]]` read raises "unbound variable".

Confirmed occurrences (grep `local.*tar_match` in `.aitask-scripts/lib/task_utils.sh`):

- Line 232 — `resolve_task_file`, child-task Tier 3 fallback
- Line 265 — `resolve_task_file`, parent-task Tier 3 fallback
- Line 324 — `resolve_plan_file`, child-plan Tier 3 fallback
- Line 353 — `resolve_plan_file`, parent-plan Tier 3 fallback (the exact site that crashed t521_3 archival)

All four are identical bugs.

## Fix

Initialize both locals at declaration in each of the four sites:

```bash
local archive_path="" tar_match=""
```

Files to modify:

- `.aitask-scripts/lib/task_utils.sh` — replace `local archive_path tar_match` → `local archive_path="" tar_match=""` at lines 232, 265, 324, 353 (all 4 occurrences).

No downstream logic change required. The `[[ -n "$tar_match" ]]` guards that gate `_extract_from_archive` are unchanged, so a real match is still the only thing that triggers extraction. The only behavioral difference is that the "`_find_archive_for_task` returned empty" path now falls through to the legacy `old.tar.*` probe cleanly instead of crashing under `set -u`.

## Verification

1. **Static check:** `shellcheck .aitask-scripts/lib/task_utils.sh` (should stay clean).
2. **Grep confirmation:** `grep -n 'local.*tar_match' .aitask-scripts/lib/task_utils.sh` shows all four lines with the `=""` form and no bare declarations remain.
3. **Unset-variable smoke test:** source the file in a subshell under `set -u` and resolve a nonexistent task ID. Before the fix this triggers the unbound-variable error in the Tier 3 branch; after the fix it returns the empty string cleanly.
   ```bash
   bash -c 'set -euo pipefail; source .aitask-scripts/lib/task_utils.sh; resolve_plan_file 999999; echo OK'
   ```
4. **Existing test suite:**
   ```bash
   bash tests/test_resolve_tar_zst.sh
   bash tests/test_archive_scan.sh
   bash tests/test_archive_utils.sh
   ```

## Post-implementation

Shared task-workflow Step 8 (review → commit `bug: Fix tar_match unbound variable in task_utils.sh (t527)`) and Step 9 (archival via `./.aitask-scripts/aitask_archive.sh 527`, then `./ait git push`).

## Final Implementation Notes

- **Actual work done:** Replaced `local archive_path tar_match` with `local archive_path="" tar_match=""` at all four Tier-3 fallback sites in `.aitask-scripts/lib/task_utils.sh` (lines 232, 265, 324, 353). No other code changes.
- **Deviations from plan:** None — fix matches the plan exactly.
- **Issues encountered:** None.
- **Key decisions:** Chose to initialize at declaration (single line change per site) rather than adding a separate default assignment after the `if`, to keep the diff minimal and the pattern uniform across all four sites.
- **Verification results:**
  - `tests/test_resolve_tar_zst.sh`: 15/15 pass
  - `tests/test_archive_scan.sh`: 23/23 pass
  - `tests/test_archive_utils.sh`: 46/46 pass
  - Smoke test `bash -c 'set -euo pipefail; source .aitask-scripts/lib/task_utils.sh; resolve_plan_file 999999'` returns cleanly under `set -u` (previously crashed on the 4th site).
  - Shellcheck: pre-existing info/warnings only; no new warnings introduced by this change.
- **Behavior change:** Purely a robustness fix. When `_find_archive_for_task` returns empty, `tar_match` is now `""` (was: unset). Downstream `[[ -n "$tar_match" ]]` guards ensure no false-positive extractions — only real matches from `_search_archive` trigger `_extract_from_archive`.
