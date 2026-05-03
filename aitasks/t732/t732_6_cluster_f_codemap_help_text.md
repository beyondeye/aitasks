---
priority: low
effort: low
depends: []
issue_type: bug
status: Ready
labels: [testing, documentation]
created_at: 2026-05-03 16:31
updated_at: 2026-05-03 16:31
---

## Context

Child 6 of t732. Cluster F: a single failing assertion in `tests/test_contribute.sh` (1 of 123). Smallest scope of all t732 children — a one-line text-match drift.

## Failing test

### tests/test_contribute.sh (122 passed / 1 failed / 123 tests)
```
FAIL: codemap help mentions shared venv (expected output containing 'shared aitasks Python')
```
Source line: `tests/test_contribute.sh:558`
```bash
assert_contains "codemap help mentions shared venv" "shared aitasks Python" "$output"
```

## Root cause hypothesis

The test asserts that `aitask_codemap.sh --help` (or the equivalent invocation in the test, see context lines 540-560) prints "shared aitasks Python" somewhere in its output. Today it does not. Either:

1. `aitask_codemap.sh`'s help text was updated and removed/renamed the string (test is stale; update the test).
2. `aitask_codemap.sh`'s help text was *supposed* to be updated to mention "shared aitasks Python" (perhaps as part of the `~/.aitask/venv` consolidation work in t695_2/3) but the update was never made (script is stale; update the help text).

Determine which by reading both:
- `tests/test_contribute.sh` lines ~540-565 (the surrounding test block — what command is it running, what other strings does it expect)
- `.aitask-scripts/aitask_codemap.sh` (the help/usage function)
- `git log --follow -p .aitask-scripts/aitask_codemap.sh | head -200` to see if the string was ever there

## Key files to investigate / modify

- `tests/test_contribute.sh:558` — the failing assertion
- `.aitask-scripts/aitask_codemap.sh` — the help text definition
- Sibling assertions on lines 559-562 (passing today): `'Only scans directories that contain git-tracked files'`, `'--include-framework-dirs'`, `'--ignore-file <path>'`, `'aidocs/'` — these CONFIRM what the help text already documents, so the new string would join that family.

## Implementation plan

1. Read `tests/test_contribute.sh:540-565` to understand the full test context.
2. Read `aitask_codemap.sh` help/usage function.
3. `git log --follow -p .aitask-scripts/aitask_codemap.sh | grep -B5 'shared aitasks Python'` to learn whether the string ever existed.
4. Decide which side is the source of truth:
   - If the string was removed from the help recently and the help still functionally documents the venv: the test should be updated to match the new wording.
   - If the help never mentioned the venv but other contexts (CLAUDE.md, README) consistently call it "shared aitasks Python": add the phrase to the help.
5. Apply the one-line fix.

## Verification

- `bash tests/test_contribute.sh` reports `123 passed / 0 failed`.
- Manual smoke: `./.aitask-scripts/aitask_codemap.sh --help` shows the consistent venv-naming string in context.
