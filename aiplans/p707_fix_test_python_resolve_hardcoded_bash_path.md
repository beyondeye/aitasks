---
Task: t707_fix_test_python_resolve_hardcoded_bash_path.md
Base branch: main
plan_verified: []
---

# Plan: Fix hard-coded `/usr/bin/bash` in test_python_resolve.sh (t707)

## Context

`tests/test_python_resolve.sh` hard-codes `/usr/bin/bash` in 8 subshell invocations. On Apple Silicon macOS the system bash 3.2 is not shipped at `/usr/bin/bash` — modern bash 5.x lives at `/opt/homebrew/bin/bash` — so the test fails immediately with:

```
tests/test_python_resolve.sh: line 101: /usr/bin/bash: No such file or directory
```

The test passes on Linux and Intel macOS (where `/usr/bin/bash` exists), so this is a portability bug that surfaced during t706 verification on an Apple Silicon Mac.

The intent of using a fully-qualified bash path was to control the subshell environment via `--noprofile --norc`. That intent is still valid; only the path resolution needs to change. Path resolution should mirror how `REAL_PY` is already resolved at the top of the file (line 42) via `command -v`.

## Approach

Resolve bash once via `command -v bash` near the top of the file, store in `TEST_BASH`, fail fast if no bash is on PATH, then replace all 8 hard-coded `/usr/bin/bash` references with `"$TEST_BASH"`.

## Critical file

- `tests/test_python_resolve.sh`

## Changes

### 1. Add `TEST_BASH` resolution after the existing `REAL_PY` block

Insert two new lines immediately after line 43 (after the `REAL_PY` empty-check block). The new block mirrors the pattern of the lines above it:

```bash
TEST_BASH="$(command -v bash)"
[[ -z "$TEST_BASH" ]] && { echo "No bash on PATH; cannot run tests."; exit 2; }
```

Place a blank line before this block to keep the visual grouping consistent with the existing file.

### 2. Replace 8 occurrences of `/usr/bin/bash`

Replace `/usr/bin/bash` with `"$TEST_BASH"` at the following lines (line numbers are pre-edit and will shift down by ~3 after the addition of the resolver block):

- Line 97  — Test 1 (system python3 fallback)
- Line 106 — Test 2 (AIT_PYTHON override)
- Line 115 — Test 3 (~/.aitask/bin/python3 precedence)
- Line 127 — Test 4 (cache stable across calls)
- Line 142 — Test 5 (require_modern_python rejects 3.9)
- Line 152 — Test 6 (require_modern_python accepts 3.13)
- Line 161 — Test 7 (require_python dies when no Python)
- Line 176 — Test 8 (double-source guard)

Each reference sits inside a double-quoted command substitution (`result="$(... /usr/bin/bash --noprofile --norc -c "..." )"`), so the replacement is a straight textual swap: `/usr/bin/bash` → `"$TEST_BASH"`. The surrounding `--noprofile --norc -c "..."` flags and quoting are unchanged.

A single `Edit` call with `replace_all: true` and `old_string: /usr/bin/bash` + `new_string: "$TEST_BASH"` is sufficient — the literal `/usr/bin/bash` does not appear elsewhere in the file.

## Verification

1. Run the test on the current Apple Silicon Mac:
   ```bash
   bash tests/test_python_resolve.sh
   ```
   Expected: `Tests: 8  Pass: 8  Fail: 0`

2. Sanity-check shellcheck on the modified file:
   ```bash
   shellcheck tests/test_python_resolve.sh
   ```
   Expected: no new warnings introduced by this change.

3. Confirm no remaining `/usr/bin/bash` occurrences:
   ```bash
   grep -n '/usr/bin/bash' tests/test_python_resolve.sh
   ```
   Expected: no output.

(Linux / Intel-Mac re-verification is not available in this environment, but `command -v bash` resolves correctly there too — `/usr/bin/bash` is on PATH and would be returned.)

## Step 9 (Post-Implementation)

After approval and implementation, follow the standard task-workflow Step 8/9: review diff, commit code under `bug: ... (t707)` then update plan with Final Implementation Notes, then archive via `./.aitask-scripts/aitask_archive.sh 707` and push.
