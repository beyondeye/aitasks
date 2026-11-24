---
Task: t2303_fix_commit_scoped_errfile_leak_on_wedge_die.md
Base branch: main
Output branch: main
---

# t2303 — commit_scoped errfile leak on wedge-die: already fixed by t2295

## Context

t2303 (spawned from t2290 on 2026-11-15) reports that `task_git_commit_scoped`
in `.aitask-scripts/lib/task_utils.sh` created `ait_commit_scoped_err.*` with
`mktemp` before `assert_data_worktree_clean`. That assert `die`s in the current
shell when the data worktree is wedged, so every wedge-die left one empty temp
file behind.

**The defect is no longer in the tree.** t2295 (commit `d657cd05c`, 2026-11-17,
two days after t2303 was created) fixed it. Its archived plan,
`aiplans/archived/p2295_fix_remaining_test_tmp_leak_producers.md:24-25`, lists
this exact defect under "Confirmed remaining defects". The current code:

- `task_git_commit_scoped` (task_utils.sh ~:1028) runs the **add** assert
  *before* the `mktemp` (lines ~1040-1046), so an already-wedged staging call
  allocates nothing.
- `_ait_commit_scoped_capture` (~:982) **unlinks** the capture file first
  thing (`rm -f -- "$_ait_cs_errf"`). After that the file lives only through the
  two open descriptors. So the later **commit** assert (~:1015) and a wedge
  that task_git's own guard catches (the seam race) leave no pathname when they
  die.
- Both asserts still run in the current shell, and their `add` / `commit`
  labels are unchanged, as t2303's "Suggested fix" requires.

t2295 also added a regression test that covers every wedge path:
`tests/test_commit_capture_cleanup.sh`. Its cases `stage_wedge`,
`no_stage_wedge`, `race` and `no_stage_busy_wedge` each check
`capture removed before outer cleanup`.

## Evidence (measured during planning, 2026-11-24, HEAD 72bdd15db)

1. **Current tree is clean.** Ran under the per-run TMPDIR guard:
   - `bash tests/run_shell_test.sh tests/test_commit_capture_cleanup.sh`: 140/140 passed, rc=0
   - `bash tests/run_shell_test.sh tests/test_task_commit_scoped.sh`: 80/80 passed, rc=0
   - `bash tests/run_shell_test.sh tests/test_issue_update_ledger.sh`: 141/141 passed, rc=0
   - `bash tests/run_shell_test.sh tests/test_task_data_writer_guard.sh`: 148/148 passed, rc=0

   None printed a `TMPDIR LEFTOVERS` line.
2. **Pre-fix control: the test detects the original defect.** The library from
   `d657cd05c^` was extracted into a throwaway directory (the work tree was not
   touched), and the current test was run against it. Exact reproduction, from
   the repository root:
   ```bash
   (
     set -euo pipefail
     prefix_lib_dir="$(mktemp -d "${TMPDIR:-/tmp}/t2303_prefix_lib.XXXXXX")"
     trap 'rm -rf -- "$prefix_lib_dir"' EXIT
     git archive d657cd05c^ .aitask-scripts/lib | tar -x -C "$prefix_lib_dir"
     test_rc=0
     CAPTURE_LIB_OVERRIDE="$prefix_lib_dir/.aitask-scripts/lib/task_utils.sh" \
         bash tests/test_commit_capture_cleanup.sh \
         > "$prefix_lib_dir/out.log" 2>&1 || test_rc=$?
     grep -E 'FAIL.*capture removed|Results' "$prefix_lib_dir/out.log"
     echo "pre-fix test exit status: $test_rc (expected 1)"
   )
   ```
   The test is expected to fail (exit 1) here. So the block runs in a subshell
   whose `EXIT` trap removes the temporary directory on every path. The test's
   status is captured with `|| test_rc=$?`, not left as a failing pipeline, so
   `errexit` / `pipefail` cannot skip the report or the cleanup. Whatever the
   calling shell's options are, the subshell keeps them from mattering.
   `tests/test_commit_capture_cleanup.sh` sources the library through
   `CAPTURE_LIB="${CAPTURE_LIB_OVERRIDE:-$SCRIPT_DIR/lib/task_utils.sh}"`. The
   test also exports `SCRIPT_DIR` to this checkout's `.aitask-scripts`, so the
   old `task_utils.sh` loads its sibling libraries (`terminal_compat.sh` etc.)
   from the current tree. Only the pre-fix `task_utils.sh` is actually used. That
   is the intended isolation: within `lib/`, t2295 changed only `task_utils.sh`
   (`git diff --stat d657cd05c^ d657cd05c -- .aitask-scripts/lib/`), and no later
   commit touches that file. So the control differs from HEAD by exactly the
   fix. The block was re-run word for word to confirm it reproduces. Result:
   136/140, and exactly the four wedge cases failed:
   ```
   FAIL: stage_wedge: capture removed before outer cleanup (expected '0', got '1')
   FAIL: no_stage_wedge: capture removed before outer cleanup (expected '0', got '1')
   FAIL: race: capture removed before outer cleanup (expected '0', got '1')
   FAIL: no_stage_busy_wedge: capture removed before outer cleanup (expected '0', got '1')
   ```
   So the same test fails on the old code and passes on the current code. This
   proves the fix is in place. It is not just a test that cannot detect the bug.

## Implementation

No code change. The task is closed as already resolved by t2295:

1. Step 7: record the risk fields (`low` / `low`) and the gates as the workflow
   requires. Do not edit any source file.
2. Step 8: present "no changes". The review consists of the evidence above.
3. Step 9 (Post-Implementation): archive t2303 with this plan as its record.
   The Final Implementation Notes say "resolved by t2295 (`d657cd05c`), no code
   change" and keep the reproduction commands above word for word, so the
   closure evidence lasts.

## Verification

- Re-run `bash tests/run_shell_test.sh tests/test_commit_capture_cleanup.sh`
  just before archival. Expect 140/140 passed and no leftovers.
- Re-run the pre-fix control block from Evidence 2 exactly as written. Expect
  `Results: 136/140 passed, 4 failed`, the four wedge `FAIL:` lines,
  `pre-fix test exit status: 1 (expected 1)` and no
  `${TMPDIR:-/tmp}/t2303_prefix_lib.*` left afterwards. Measured during
  planning: the block, extracted from this plan and checked byte-identical, was
  run under `bash -euo pipefail`. It printed exactly that, the outer rc was 0,
  and 0 leftover directories remained.

## Risk

### Code-health risk: low
None identified. No source change is made.

### Goal-achievement risk: low
None identified. The defect's absence has positive evidence: a regression test
that fails on the pre-fix library and passes on the current one.
