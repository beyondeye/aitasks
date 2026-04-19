---
Task: t583_6_issue_type_manual_verification_and_unit_tests.md
Parent Task: aitasks/t583_manual_verification_module_for_task_workflow.md
Sibling Tasks: aitasks/t583/t583_1_*.md .. t583_9_*.md
Archived Sibling Plans: aiplans/archived/p583/p583_*_*.md
Worktree: (current branch)
Branch: (current branch)
Base branch: main
---

# Plan: t583_6 — `manual_verification` Issue Type + Unit Tests

## Context

Registers the new `manual_verification` issue type in both the live and seed task_types lists; writes unit tests for the helpers delivered in t583_1, t583_2, t583_3.

Depends on t583_1, t583_2, t583_3.

## Files to modify / create

**Modify:**
- `aitasks/metadata/task_types.txt` (add `manual_verification`)
- `seed/aitasks/metadata/task_types.txt` (mirror)

**New:**
- `tests/test_verification_parse.sh`
- `tests/test_verification_followup.sh`
- `tests/test_verifies_field.sh`

## Test coverage

### `test_verification_parse.sh`
- No section / empty section / all pending / mixed states / malformed checkboxes.
- H2 case-insensitivity (`## VERIFICATION`, `## Checklist`, `## Verification checklist`).
- `set` adds correct timestamp + note; round-trip preserves state.
- `terminal_only` exit codes: all terminal → 0; pending → 2 w/ `PENDING:N`; defer → 2 w/ `DEFERRED:N`.
- `seed` on fresh task file → parsable checklist afterward.

### `test_verification_followup.sh`
- Temp git repo with a commit like `feature: test (tFAKE)`.
- Manual-verification task with `verifies:[FAKE]` + 1 fail item.
- Happy path: `FOLLOWUP_CREATED:` present; new bug task description contains commit hash, file, failing text.
- Ambiguous origin: `verifies:[FAKE,FAKE2]` → exits 2 with `ORIGIN_AMBIGUOUS:FAKE,FAKE2`.
- Back-reference: if archived plan fixture exists, helper appends a line under `## Final Implementation Notes`.

### `test_verifies_field.sh`
- Create round-trip with `--verifies 10,11`.
- Update add/remove.
- Fold union on 2 tasks with overlapping `verifies:`.

## Reference precedent

- `tests/test_claim_id.sh` — harness (`assert_eq`, `assert_contains`).
- Other `tests/test_*.sh` — style.

## Verification

- `bash tests/test_verification_parse.sh` → all PASS.
- `bash tests/test_verification_followup.sh` → all PASS.
- `bash tests/test_verifies_field.sh` → all PASS.
- `shellcheck tests/test_verification_*.sh` → no warnings.

## Final Implementation Notes

_To be filled in during implementation._
