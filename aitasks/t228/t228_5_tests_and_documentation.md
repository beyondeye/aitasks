---
priority: medium
effort: medium
depends: [t228_3]
issue_type: test
status: Implementing
labels: [aitask_board]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-02-24 09:14
updated_at: 2026-02-24 11:38
---

## Add tests for merge script and update documentation

### Context

The auto-merge system (t228_1 through t228_3) needs comprehensive testing and documentation. This includes Python unit tests for the merge script, bash integration tests for the sync+merge flow, and user-facing documentation.

Part of t228 "Improved Task Merge for ait sync". Depends on t228_3 (can be done in parallel with t228_4).

### Key Files to Modify

- `tests/test_aitask_merge.py` (NEW) — Python unit tests for merge script
- `tests/test_sync_merge.sh` (NEW) — Bash integration tests for sync+merge

### Reference Files for Patterns

- `tests/test_sync.sh` — Existing sync test patterns (`setup_sync_repos()`, `assert_eq`, `assert_contains`)
- `aiscripts/board/aitask_merge.py` — The merge script to test (from t228_2)
- `aiscripts/aitask_sync.sh` — The sync script with merge integration (from t228_3)

### Implementation Plan

#### 1. Python Unit Tests (`tests/test_aitask_merge.py`)

Use Python's `unittest` (no external test framework dependency). Test cases:

**Conflict marker parsing:**
- `test_full_file_conflict` — entire file is one conflict hunk
- `test_frontmatter_only_conflict` — only frontmatter differs, body identical
- `test_body_only_conflict` — frontmatter identical, body differs
- `test_no_conflict_markers` — file has no conflict markers (exit 1)
- `test_no_frontmatter` — file has conflict markers but no YAML frontmatter (exit 1)

**Auto-merge rules:**
- `test_boardcol_keeps_local` — boardcol/boardidx: LOCAL wins
- `test_updated_at_keeps_newer` — updated_at: newer timestamp wins
- `test_labels_union` — labels: union of both lists, deduplicated
- `test_depends_union` — depends: union of both lists, deduplicated
- `test_priority_keeps_remote_batch` — priority: REMOTE in batch mode
- `test_effort_keeps_remote_batch` — effort: REMOTE in batch mode
- `test_status_implementing_wins` — status: Implementing takes precedence
- `test_status_both_non_implementing_unresolved` — status: neither Implementing → unresolved

**Field presence:**
- `test_field_only_in_local` — field exists only in LOCAL → keep it
- `test_field_only_in_remote` — field exists only in REMOTE → keep it
- `test_field_same_both_sides` — field same in both → keep it (no conflict)

**Edge cases:**
- `test_empty_labels_merge` — one side has empty labels, other has some
- `test_both_implementing_status` — both sides Implementing → keep (same value)
- `test_newest_hint_in_output` — verify stderr contains newest hints for unresolved fields

**Exit codes and stdout:**
- `test_exit_0_fully_resolved` — all conflicts auto-merged
- `test_exit_1_not_task_file` — file without frontmatter
- `test_exit_2_partial` — some fields unresolvable

#### 2. Bash Integration Tests (`tests/test_sync_merge.sh`)

Follow the `test_sync.sh` pattern with `setup_sync_repos()`:

- `test_automerge_boardcol_conflict` — conflicting boardcol changes → AUTOMERGED
- `test_automerge_labels_conflict` — conflicting label changes → merged union
- `test_automerge_mixed_fields` — multiple auto-resolvable fields at once
- `test_unresolvable_conflict` — status conflict (non-Implementing) → CONFLICT:
- `test_partial_merge` — some fields auto-merged, body conflict remains
- `test_no_python_fallback` — rename venv → graceful fallback to CONFLICT:
- `test_implementing_status_wins` — remote sets Implementing, local changes something else
- `test_automerge_then_push` — verify auto-merged changes are committed and pushed

#### 3. Documentation

Update website docs to document:
- Auto-merge rules table
- New `AUTOMERGED` batch status
- How to customize merge behavior (future)
- Troubleshooting: what to do when auto-merge can't resolve

### Verification Steps

1. Run Python tests: `python3 -m pytest tests/test_aitask_merge.py -v` (or `python3 -m unittest tests.test_aitask_merge -v`)
2. Run bash tests: `bash tests/test_sync_merge.sh`
3. Run existing sync tests to confirm no regressions: `bash tests/test_sync.sh`
