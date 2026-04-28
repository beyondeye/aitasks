---
Task: t680_skip_test_codex_model_detect_when_codex_unavailable.md
Worktree: (current branch)
Branch: main
Base branch: main
---

# Plan: skip test_codex_model_detect.sh when codex CLI unavailable

## Context

`tests/test_codex_model_detect.sh` is part of the macOS audit baseline (t658). On hosts where the Codex CLI isn't installed, it currently prints `ERROR: codex CLI not found in PATH` and exits 1, which causes the test suite to fail rather than skipping. The desired behavior — already followed by `tests/test_multi_session_primitives.sh:130` for missing tmux — is to print a `SKIP:` line and exit 0 so the test is treated as inapplicable, not failing.

## Change

`tests/test_codex_model_detect.sh:103-110` currently has:

```bash
if ! command -v codex &>/dev/null; then
    echo "ERROR: codex CLI not found in PATH" >&2
    exit 1
fi
if ! command -v jq &>/dev/null; then
    echo "ERROR: jq not found in PATH" >&2
    exit 1
fi
```

Replace with:

```bash
if ! command -v codex &>/dev/null; then
    echo "SKIP: codex CLI not installed — skipping test"
    exit 0
fi
if ! command -v jq &>/dev/null; then
    echo "SKIP: jq not installed — skipping test"
    exit 0
fi
```

Both prerequisites get the same skip-not-fail treatment, since both are external dependencies whose absence makes the test inapplicable rather than broken. Output goes to stdout (not stderr) to match the reference pattern in `test_multi_session_primitives.sh:131`.

## Files to modify

- `tests/test_codex_model_detect.sh` (lines 103-110)

## Reference pattern

`tests/test_multi_session_primitives.sh:130` — `if ! command -v tmux >/dev/null 2>&1; then echo "SKIP: ..."; ...`

## Verification

- On this host (no `codex` in PATH): `bash tests/test_codex_model_detect.sh` → prints `SKIP: codex CLI not installed — skipping test`, exits 0.
- Confirm exit code: `bash tests/test_codex_model_detect.sh; echo $?` → `0`.
- The `jq` skip path is symmetric and verified by code inspection (we cannot easily simulate missing jq on this host without uninstalling).
- On a host with both `codex` and `jq`: behavior unchanged — falls through to the existing test body. (Not exercisable on this host; presumed safe — the existing assertions were not regressed by t658, only the prerequisite exit codes change.)

## Step 9 (Post-Implementation)

Standard archival flow per `task-workflow/SKILL.md` Step 9: commit (`test: Skip test_codex_model_detect.sh when codex/jq unavailable (t680)`), then `aitask_archive.sh 680`, push.

## Final Implementation Notes

- **Actual work done:** Replaced the two prerequisite-error blocks at `tests/test_codex_model_detect.sh:103-110` so that a missing `codex` or `jq` prints a `SKIP:` line to stdout and exits 0, matching the convention in `tests/test_multi_session_primitives.sh:130`.
- **Deviations from plan:** None.
- **Issues encountered:** None.
- **Key decisions:** Mirrored the reference pattern exactly — `SKIP:` to stdout (not stderr), `exit 0`. Applied symmetric handling to the `jq` block since `jq` is also an external dependency whose absence makes the test inapplicable, not broken.
- **Upstream defects identified:** None.
- **Verification performed:** Ran `PATH=/usr/bin:/bin bash tests/test_codex_model_detect.sh; echo "EXIT=$?"` — output `SKIP: codex CLI not installed — skipping test` followed by `EXIT=0`. Codex is present on this dev host so the codex-present pass-through was confirmed only insofar as the script ran past the prereq guard into the actual test loop before being interrupted (the full 24-run test would have taken ~12 minutes; not relevant to this task's scope).
