---
priority: high
effort: high
depends: [t228_1]
issue_type: feature
status: Done
labels: [aitask_board]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-02-24 09:14
updated_at: 2026-02-24 10:24
completed_at: 2026-02-24 10:24
---

## Create Python auto-merge script for task metadata conflicts

### Context

When `ait sync` encounters git merge conflicts in task files, all conflicts currently require manual resolution. Most task metadata conflicts are trivially resolvable with well-defined rules. This script implements those auto-merge rules.

Part of t228 "Improved Task Merge for ait sync". Depends on t228_1 which extracts shared YAML utilities.

### Key Files to Modify

- `aiscripts/board/aitask_merge.py` (NEW) — Core merge logic

### Reference Files for Patterns

- `aiscripts/board/task_yaml.py` — Shared YAML utilities from t228_1 (`parse_frontmatter`, `serialize_frontmatter`, `_TaskSafeLoader`, `_FlowListDumper`)
- `aiscripts/board/aitask_board.py` lines 190-203 — `reload_and_save_board_fields()` as an existing merge pattern example
- `aiscripts/aitask_sync.sh` lines 189-254 — `do_pull_rebase()` for context on how conflict markers are generated

### Implementation Plan

#### 1. CLI Interface

```
python3 aiscripts/board/aitask_merge.py <conflicted_file> [--batch] [--data-worktree <path>]
```

**Exit codes:**
- `0`: File fully resolved, safe to `git add`
- `1`: Not a task file, parse error, or IO error (skip auto-merge)
- `2`: Partial resolution — some fields or body content need manual attention

**Stdout protocol:**
- `RESOLVED` — Fully auto-merged
- `PARTIAL:<field1>,<field2>` — Some fields could not be auto-resolved
- `SKIPPED` — Not a task file (no frontmatter)
- `ERROR:<message>` — Parse/IO error

**Stderr:** Informational messages (what was auto-merged, newest hints for manual fields)

#### 2. Conflict Marker Parser

Parse git conflict markers (`<<<<<<<`, `=======`, `>>>>>>>`) from the file to extract LOCAL and REMOTE versions:

```python
def parse_conflict_file(content: str) -> tuple[str, str] | None:
    """Extract LOCAL and REMOTE versions from git conflict markers.

    Returns (local_content, remote_content) or None if no conflict markers.
    Handles entire-file conflicts and multi-hunk conflicts.
    """
```

For task files, the entire frontmatter+body is typically one conflict hunk. The parser should reconstruct the complete LOCAL and REMOTE documents.

#### 3. Auto-Merge Rules

```python
def merge_frontmatter(local_meta: dict, remote_meta: dict,
                      batch: bool = False) -> tuple[dict, list[str]]:
    """Merge two frontmatter dicts according to auto-merge rules.

    Returns (merged_meta, unresolved_fields).
    """
```

**Rules (all fields):**

| Field | Strategy |
|-------|----------|
| `boardcol`, `boardidx` | Keep LOCAL |
| `updated_at` | Keep LATEST (parse timestamps, compare) |
| `labels` | Union of both lists, deduplicated, sorted |
| `depends` | Union of both lists, deduplicated, sorted |
| `priority`, `effort` | Keep REMOTE in batch mode; in interactive mode, print both with newest hint and prompt user |
| `status` | If either side is `Implementing` and other is not → keep `Implementing`. Otherwise → unresolvable |
| All other differing fields | Add to unresolved list |

**Field present on one side only:** Union of all keys — no conflict, just include the field.

**Newest hint:** For unresolvable fields, compare `updated_at` from each side and annotate stderr output:
```
status conflict: LOCAL="Done" (newer: 2026-02-24 09:00) vs REMOTE="Postponed" (2026-02-24 08:30)
```

#### 4. Body Merge

If the body (markdown content below frontmatter) differs between LOCAL and REMOTE:
- Cannot auto-merge → add "body" to unresolved fields
- When partially resolved (frontmatter OK, body not), write frontmatter merged + body with conflict markers retained

#### 5. File Output

If fully resolved: write merged content to the original file path.
If partially resolved: write what can be merged, keep conflict markers for unresolved parts.

### Verification Steps

1. Create a test task file with conflict markers manually, run the script, verify output
2. Test each merge rule individually (see t228_5 for full test plan)
3. Test edge cases: no frontmatter, empty file, malformed YAML, body-only conflict
4. Verify the script can be called from bash: `python3 aiscripts/board/aitask_merge.py test_file.md --batch; echo $?`
