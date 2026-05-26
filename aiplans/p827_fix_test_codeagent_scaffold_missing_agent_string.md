---
Task: t827_fix_test_codeagent_scaffold_missing_agent_string.md
Worktree: (current working directory)
Branch: main
Base branch: main
---

## Problem

`tests/test_codeagent.sh` fails at "Test 2: list-agents" because
`.aitask-scripts/aitask_codeagent.sh:18` sources `lib/agent_string.sh`, but
the test's `setup_test_env()` does not copy that lib into the fake repo's
`.aitask-scripts/lib/`.

## Fix

Add a single `cp` line in `tests/test_codeagent.sh::setup_test_env()`
alongside the existing inline lib copies (`task_utils.sh`,
`archive_utils.sh`), copying `agent_string.sh` to the fake repo.

Per CLAUDE.md baseline and t827's "Approach" section, do NOT add this to
`tests/lib/test_scaffold.sh::setup_fake_aitask_repo()` — `agent_string.sh`
is a domain helper, not a system lib in `./ait`'s source-on-startup chain.

## Implementation

In `tests/test_codeagent.sh`, around line 89-90:

```bash
cp "$PROJECT_DIR/.aitask-scripts/lib/task_utils.sh" "$tmpdir/.aitask-scripts/lib/"
cp "$PROJECT_DIR/.aitask-scripts/lib/archive_utils.sh" "$tmpdir/.aitask-scripts/lib/"
cp "$PROJECT_DIR/.aitask-scripts/lib/agent_string.sh" "$tmpdir/.aitask-scripts/lib/"
```

## Verification

- `bash tests/test_codeagent.sh` reaches all assertions and exits 0.
- No edit to `tests/lib/test_scaffold.sh`.
