---
Task: t2079_fix_cd_guard_lint_violations_in_three_tests.md
Base branch: main
Output branch: main
---

# t2079 — Fix cd-guard lint violations in three tests

## Context

`bash tests/test_cd_guard_lint.sh` reports `Results: 90 passed, 2 failed`
(reproduced on the current tree, 2026-10-20). The two failing assertions name
three pre-existing sites, none of which t2073_1 touched:

1. `tests/test_ait_git_gateway_pull.sh:769` — `unconfined-andchain`:
   `(unset AIT_P5_UNSET; cd "$FX_LOCAL" && ./ait git … push --batch)`. The scanner
   (`tests/lib/cd_guard_scan.py`, `_chain_opener`) only accepts a cd that is the
   **first** command of the `(` group, joined by `&&` only; the leading
   `unset …;` breaks that. The task warned this file was being edited
   concurrently — re-checked: the line is still at 769 and the file is clean in
   `git status`.
2. `tests/test_archive_rearm_exit_trap.sh` — no `enter_scratch_cwd` call (first cd
   at line 262).
3. `tests/test_session_hook.sh` — no `enter_scratch_cwd` call (first cd at line 429).

Goal: the lint reports 0 failed, and each of the three suites still passes.

## Implementation

### 1. `tests/test_ait_git_gateway_pull.sh:769`

Move the cd to the front of the group and fold `unset` into the `&&` chain
(`unset` of a named variable returns 0, so the chain still runs the push):

```bash
(cd "$FX_LOCAL" && unset AIT_P5_UNSET && ./ait git --config-env=remote.origin.url=AIT_P5_UNSET push --batch) \
    >"$FX/run_out" 2>"$FX/run_err"
```

Semantics unchanged: the variable is still unset only inside the subshell, before
`./ait` runs; a failed cd still runs nothing.

### 2. `tests/test_archive_rearm_exit_trap.sh` and 3. `tests/test_session_hook.sh`

Insert, right after the `PROJECT_DIR=` line and before sourcing `asserts.sh` —
the exact pattern used in `tests/test_ait_git_gateway_pull.sh:14-19`:

```bash
# Start from an empty read-only dir, never the invoking one (t1826).
. "$PROJECT_DIR/tests/lib/scratch_cwd.sh"
enter_scratch_cwd
```

Pre-checks done: neither file captures `$(pwd)`/`$PWD` before that point, and
the `dirname "${BASH_SOURCE[0]}"` derivation is on the `SCRIPT_DIR=` line *before*
the call (allowed by `helper_order`). All fixture dirs come from `mktemp -d`
(absolute) — `FIX`/`PROJ`/`PROBE` in the archive test, `TMP`/`ROOT`/`ARGV_DIR`
in the session-hook test — so the read-only cwd should not break any relative
write. Verification below confirms this.

## Verification

```bash
bash tests/test_cd_guard_lint.sh                 # expect: 0 failed
python3 tests/lib/cd_guard_scan.py --check tests/test_ait_git_gateway_pull.sh
python3 tests/lib/cd_guard_scan.py --helper-order tests/test_archive_rearm_exit_trap.sh tests/test_session_hook.sh
bash tests/test_ait_git_gateway_pull.sh          # P5 assertions still pass
bash tests/test_archive_rearm_exit_trap.sh
bash tests/test_session_hook.sh
shellcheck tests/test_ait_git_gateway_pull.sh tests/test_archive_rearm_exit_trap.sh tests/test_session_hook.sh
```

Then Step 9 (Post-Implementation): current-branch mode, no merge; archive via
`aitask_archive.sh 2079`.

## Risk

### Code-health risk: low
None identified.

### Goal-achievement risk: low
None identified.
