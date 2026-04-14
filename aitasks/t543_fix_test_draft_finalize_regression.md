---
priority: medium
effort: low
depends: []
issue_type: bug
status: Implementing
labels: [testing, bash_scripts]
file_references: [tests/test_draft_finalize.sh, .aitask-scripts/aitask_create.sh:13]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-04-14 11:27
updated_at: 2026-04-14 11:30
---

tests/test_draft_finalize.sh fails with 25/35 failing on main (pre-existing, not caused by t540_1).

## Symptoms

```
bash tests/test_draft_finalize.sh
# Results: 10 passed, 25 failed, 35 total
```

The setup_draft_project() helper copies a subset of scripts and libs into a temporary repo, but does NOT copy .aitask-scripts/lib/archive_utils.sh nor .aitask-scripts/lib/archive_scan.sh. aitask_create.sh sources lib/archive_utils.sh at line 13, and aitask_claim_id.sh sources lib/archive_scan.sh. Both sourcing operations fail in the isolated test harness, which cascades into every test that calls aitask_create.sh --batch or aitask_claim_id.sh --init.

## Reproduction

Stash any local changes and run:

```bash
git stash
bash tests/test_draft_finalize.sh   # 10 passed, 25 failed, 35 total
git stash pop
```

The same breakage is visible on a clean `main`.

## Fix

In tests/test_draft_finalize.sh setup_draft_project(), add the two missing lib files to the cp block:

```bash
cp "$PROJECT_DIR/.aitask-scripts/lib/archive_utils.sh" .aitask-scripts/lib/
cp "$PROJECT_DIR/.aitask-scripts/lib/archive_scan.sh" .aitask-scripts/lib/
```

The pattern that works is already in tests/test_file_references.sh (added by t540_1) — use that as the reference.

## Verification

```bash
bash tests/test_draft_finalize.sh   # should reach "ALL TESTS PASSED"
```

## Context

Discovered during t540_1 implementation while running regression checks per plan verification. The fix is mechanical (copy two files) and isolated to the test harness — no production code changes needed.
