---
Task: t543_fix_test_draft_finalize_regression.md
Worktree: (none — working on current branch)
Branch: main
Base branch: main
---

# Plan: Fix test_draft_finalize.sh regression (t543)

## Context

`bash tests/test_draft_finalize.sh` currently fails 25/35 tests on a clean `main`. The failure is pre-existing (not introduced by t540_1) and has a single mechanical root cause:

`setup_draft_project()` builds a temporary repo by copying a curated subset of scripts and lib files into `.aitask-scripts/`, but it omits:
- `.aitask-scripts/lib/archive_utils.sh`
- `.aitask-scripts/lib/archive_scan.sh`

Both libs are required because:
- `aitask_create.sh:13` does `source "$SCRIPT_DIR/lib/archive_utils.sh"`
- `aitask_claim_id.sh:26` does `source "$SCRIPT_DIR/lib/archive_scan.sh"`

Sourcing fails inside the test harness (file missing), and the failure cascades into every test that calls `aitask_create.sh --batch` or `aitask_claim_id.sh --init`. The fix is mechanical: copy the two libs into the harness alongside the existing two libs.

The same pattern was already added to `tests/test_file_references.sh` (lines 91–92) when `t540_1` introduced `archive_utils.sh`/`archive_scan.sh` — that file is the reference.

## Change

**File:** `tests/test_draft_finalize.sh`

In `setup_draft_project()`, after the existing `cp` block (currently at lines 103–104):

```bash
cp "$PROJECT_DIR/.aitask-scripts/lib/terminal_compat.sh" .aitask-scripts/lib/
cp "$PROJECT_DIR/.aitask-scripts/lib/task_utils.sh" .aitask-scripts/lib/
```

…add the same two `cp` lines used by `tests/test_file_references.sh:91-92`:

```bash
cp "$PROJECT_DIR/.aitask-scripts/lib/archive_utils.sh" .aitask-scripts/lib/ 2>/dev/null || true
cp "$PROJECT_DIR/.aitask-scripts/lib/archive_scan.sh" .aitask-scripts/lib/ 2>/dev/null || true
```

The `2>/dev/null || true` guard mirrors the reference pattern, keeping the harness resilient if a future branch ever drops these libs.

That is the entire change — no other files are modified.

## Verification

```bash
bash tests/test_draft_finalize.sh
```

Expected: `Results: 35 passed, 0 failed, 35 total` followed by `ALL TESTS PASSED`.

Spot-check that no other test file is silently relying on the same harness — `tests/test_draft_finalize.sh` is self-contained, so no other test should be affected.

## Step 9 (Post-Implementation)

- No worktree to clean up (working on current branch).
- Commit code change with `bug: <description> (t543)`.
- Plan file: this plan documents the fix; final implementation notes will be added during Step 8 consolidation.
- Run `./.aitask-scripts/aitask_archive.sh 543` to archive task and plan.
- Push with `./ait git push`.
