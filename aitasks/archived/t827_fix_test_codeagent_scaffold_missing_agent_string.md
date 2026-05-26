---
priority: medium
effort: low
depends: [790]
issue_type: bug
status: Done
labels: [testing, test_infrastructure]
assigned_to: dario-e@beyond-eye.com
implemented_with: claudecode/opus4_7_1m
created_at: 2026-05-25 18:04
updated_at: 2026-05-26 18:23
completed_at: 2026-05-26 18:23
boardidx: 100
---

## Context

Surfaced by t790 triage of pre-existing test failures
(`aiplans/p790_triage_preexisting_test_failures_post_t777.md`, Bucket A).

`tests/test_codeagent.sh` fails at "Test 2: list-agents" because
`aitask_codeagent.sh:18` sources `lib/agent_string.sh`, but the test
scaffolder does not copy that lib into the fake repo. Symptom:

```
.aitask-scripts/aitask_codeagent.sh: line 18:
.../lib/agent_string.sh: No such file or directory
```

## Approach

`agent_string.sh` is a domain helper sourced by `aitask_codeagent.sh`, not a
system lib in `./ait`'s source-on-startup chain. Per p734's "the helper is
the floor, not a ceiling" guidance and the CLAUDE.md baseline
(`aitask_path.sh`, `terminal_compat.sh`, `python_resolve.sh`), add the copy
inline in `tests/test_codeagent.sh` after `setup_fake_aitask_repo` returns
— do NOT add it to `tests/lib/test_scaffold.sh::setup_fake_aitask_repo()`.

Verify with `bash tests/test_codeagent.sh` — the run should reach all
existing assertions and exit zero (or fail on real assertions, not the
missing-file error).

## Out of scope

- Other Bucket B / C failures from t790.
- Refactoring the scaffold helper for domain libs in general.

## Verification

- `bash tests/test_codeagent.sh` exits 0 (or fails for unrelated reasons
  that this task explicitly notes).
- Whole-suite regression loop (p734 §3) shows `test_codeagent.sh` removed
  from the FAIL list.
- No new copy line added to `tests/lib/test_scaffold.sh` — the change is
  local to `tests/test_codeagent.sh`.
