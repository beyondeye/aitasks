---
priority: medium
effort: medium
depends: [t583_1, t583_2, t583_3]
issue_type: test
status: Implementing
labels: [framework, skill, task_workflow, verification, testing]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-04-19 08:29
updated_at: 2026-04-19 14:48
---

## Context

Sixth child of t583. Registers the new `manual_verification` issue type and writes unit tests for the helpers delivered in t583_1, t583_2, t583_3.

Depends on t583_1 (parser helper exists), t583_2 (verifies field plumbing exists), t583_3 (followup helper exists).

## Key Files to Modify

- `aitasks/metadata/task_types.txt` — add `manual_verification` line.
- `seed/aitasks/metadata/task_types.txt` — mirror.
- `tests/test_verification_parse.sh` — **new file**.
- `tests/test_verification_followup.sh` — **new file**.
- `tests/test_verifies_field.sh` — **new file**.

## Reference Files for Patterns

- `tests/test_claim_id.sh` — reference for test harness (uses `assert_eq`, `assert_contains` helpers, prints PASS/FAIL summary).
- Other `tests/test_*.sh` — consistent style.

## Implementation Plan

### 1. `task_types.txt` registration

Append `manual_verification` to both files. One-line change each.

### 2. `test_verification_parse.sh`

Fixtures:
- **No section:** task file with no verification section → `parse` empty, `summary TOTAL:0`.
- **Empty section:** `## Verification Checklist` with no items → `TOTAL:0`.
- **All pending:** 3 items, all unchecked → `parse` emits 3 lines, all `pending`.
- **Mixed states:** one of each — `pending`, `pass`, `fail`, `skip`, `defer` → 5 lines with correct states.
- **Malformed checkboxes:** lines like `- [Y]` or `- [ok]` → ignored (not items).
- **H2 case-insensitivity:** `## VERIFICATION`, `## Checklist`, `## Verification checklist` all recognized.
- **Suffix round-trip:** `set ... pass` then `parse` → item's pass state is preserved across round-trip.
- **`set` adds timestamp + note:** after `set <id> fail --note "foo"`, the line contains `— FAILED` + ISO timestamp + `foo`.
- **`terminal_only` exits:** all terminal → exit 0; any pending → exit 2 with `PENDING:N`; any defer → exit 2 with `DEFERRED:N`.
- **`seed` subcommand:** create fresh task file, seed with 3-line items file, parse → 3 pending items.

### 3. `test_verification_followup.sh`

- **Setup:** create a fake git repo in a temp dir; commit a file with message `feature: test feature (tFAKE)`; create a manual-verification task with `verifies: [FAKE]` and one fail item.
- **Happy path:** invoke followup with `--from <id> --item 1` → `FOLLOWUP_CREATED:` line present; new bug task file exists; description contains the commit hash, touched file, and failing-item text.
- **Ambiguous origin:** `verifies: [FAKE, FAKE2]` → followup (without `--origin`) exits 2 with `ORIGIN_AMBIGUOUS:FAKE,FAKE2`.
- **Back-reference:** if archived plan exists for origin, helper appends a line under `## Final Implementation Notes`. Test fixture provides a minimal archived plan file.

### 4. `test_verifies_field.sh`

- `create` round-trip: `aitask_create.sh --batch --type manual_verification --name test --verifies 10,11 --commit` → file has `verifies: [10, 11]`.
- `update` add/remove: `aitask_update.sh --batch <id> --add-verifies 12` → `verifies: [10, 11, 12]`; then `--remove-verifies 10` → `verifies: [11, 12]`.
- `fold` union: create 2 tasks with `verifies: [A, B]` and `[B, C]` respectively; fold both into a third → third's `verifies:` is `[A, B, C]` (union, no dupes).

### 5. Test execution

All three tests runnable via `bash tests/test_verification_parse.sh` etc. They must clean up temp files and git repos on exit.

## Verification Steps

- Run all three new test scripts individually; all assertions pass.
- Run `shellcheck tests/test_verification_*.sh` — no warnings.
- `cat aitasks/metadata/task_types.txt | grep manual_verification` — returns the line.

## Step 9 reminder

Commit: `test: Add manual-verification unit tests and register issue type (t583_6)`.
