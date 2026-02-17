---
Task: t150_bug_in_create_new_release.md
Branch: main
---

# Fix: EXIT trap corrupts exit code in aitask_changelog.sh (t150)

## Context

`create_new_release.sh` reports "No CHANGELOG.md entry found for v0.4.0" even though `CHANGELOG.md` has a valid `## v0.4.0` entry. The root cause is in `task_utils.sh`: the EXIT trap cleanup function returns non-zero when no temp directory was created, which overrides the script's exit code in bash 5.3.9 with `set -e`.

## Root Cause

In `aiscripts/lib/task_utils.sh` lines 22-24:
```bash
_ait_task_utils_cleanup() {
    [[ -n "$_AIT_TASK_UTILS_TMPDIR" && -d "$_AIT_TASK_UTILS_TMPDIR" ]] && rm -rf "$_AIT_TASK_UTILS_TMPDIR"
}
```

When `_AIT_TASK_UTILS_TMPDIR=""` (no tar extraction happened, as in `--check-version` mode):
- `[[ -n "" ... ]]` → false → `&& rm` skipped → command returns 1
- EXIT trap returns 1 → overrides script's exit code 0 → caller sees failure

## Changes

- [x] 1. Fix `_ait_task_utils_cleanup` in `aiscripts/lib/task_utils.sh` — replace `[[ ]] && rm` with `if/then/fi`
- [x] 2. Harden grep pattern in `aiscripts/aitask_changelog.sh` — allow trailing whitespace

## Verification

1. `./aiscripts/aitask_changelog.sh --check-version 0.4.0; echo $?` → should be 0
2. `./aiscripts/aitask_changelog.sh --check-version 99.99.99; echo $?` → should be 1
3. `bash tests/test_resolve_tar_gz.sh` → all tests pass

## Final Implementation Notes
- **Actual work done:** Fixed the EXIT trap cleanup function in `task_utils.sh` that was corrupting script exit codes. Also hardened the changelog version grep pattern to tolerate trailing whitespace.
- **Deviations from plan:** None — both planned changes implemented as designed.
- **Issues encountered:** None — the root cause was confirmed: `[[ ]] && rm` returns exit code 1 when the condition is false, and in bash 5.3.9 with `set -e`, this overrides the script's intended exit code when the EXIT trap fires.
- **Key decisions:** Used `if/then/fi` instead of `|| true` because it's more idiomatic and doesn't mask potential `rm` failures.
