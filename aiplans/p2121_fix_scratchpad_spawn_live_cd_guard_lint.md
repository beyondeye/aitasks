---
Task: t2121_fix_scratchpad_spawn_live_cd_guard_lint.md
Base branch: main
Output branch: main
---

# t2121 — Fix cd-guard lint failures in tests/test_scratchpad_spawn_live.sh

## Context

`bash tests/test_cd_guard_lint.sh` fails twice. Both failures come from
`tests/test_scratchpad_spawn_live.sh`, which was added by t2088 (4da69fcfb):

1. `tests/test_scratchpad_spawn_live.sh:218:unconfined-andchain`. `key_for()` runs
   `(cd "$1" && if …; then …; else …; fi)`. The scanner reads the `;` inside the
   `if` as `a; b`, so it treats everything after the first `;` as running in
   the old cwd.
2. `no enter_scratch_cwd call (first cd at line 218)`. The file changes its cwd
   but never enters the read-only scratch cwd.

Both failures were reproduced with `python3 tests/lib/cd_guard_scan.py --check` /
`--helper-order` on the current file. The convention is in
`aidocs/framework/testing_conventions.md` ("Every `cd` in a bash test is
`exit`-guarded"). t2079 (37e2d640d) fixed the same failures in three other tests.

## Implementation

Only one file changes: `tests/test_scratchpad_spawn_live.sh`.

1. **Add `enter_scratch_cwd`** right after `PROJECT_DIR=` (line 43) and before the
   `command -v tmux` SKIP line. Use the same block that t2079 and
   `tests/test_frozen_agents_acceptance.sh:75-77` use:
   ```bash
   # Start from an empty read-only dir, never the invoking one (t1826).
   . "$PROJECT_DIR/tests/lib/scratch_cwd.sh"
   enter_scratch_cwd
   ```
   The cwd-safety audit found nothing that depends on the starting cwd:
   - every path in the file is absolute (`$PROJECT_DIR`/`$FIXTURE_DIR`);
   - tmux panes get `-c "$ROOT"`;
   - the driver gets an absolute `PYTHONPATH`;
   - `tests/lib/frozen_fixtures.sh` has no `cd`/`pwd`/`PWD`/`git` use;
   - the `ait` shim's `$PWD` is the pane's cwd (`-c`), not the test's.

   Two other live tests already combine `enter_scratch_cwd` with
   `frozen_fixtures.sh` (`test_frozen_agents_acceptance.sh`,
   `test_linked_trail_jump_live.sh`).

2. **Rewrite `key_for()`** into the guarded form. Behaviour does not change: the
   store helper still runs from `<root>`. If the `cd` fails, the subshell exits 1
   with empty output, and the A-case `assert_eq` fails visibly.
   ```bash
   key_for() {  # key_for <root> <task> [<AITASK_SCRATCHPAD_DIR>|""]
       (cd "$1" || exit 1
        if [ -n "${3:-}" ]; then AITASK_SCRATCHPAD_DIR="$3" "$STORE_SH" path "$2"
        else env -u AITASK_SCRATCHPAD_DIR "$STORE_SH" path "$2"; fi)
   }
   ```
   During planning I fed exactly this form to `cd_guard_scan.py --check`. It
   returned rc=0 with no violations.

### Post-phase (risk mitigations)

1. [keyfor_standalone_equivalence] The live test cannot run from this session,
  so exercise the rewritten `key_for` on its own from the scratch cwd
  (`$TMPDIR/ait-test-cwd-$UID`). Run it against the real
  `.aitask-scripts/aitask_scratchpad_store.sh` with:
  - both arg shapes: with a pad dir, and with an empty third arg;
  - root = `$PROJECT_DIR`, and a fixture `AITASK_SCRATCHPAD_DIR`.

  Then assert that its output is byte-identical to the old `(cd … && if …)` form.
  As a control, a nonexistent root must make it print nothing and exit 1.

## Verification

- `bash tests/test_cd_guard_lint.sh` → 92 passed, 0 failed. Before the fix it
  reported 90/2.
- `shellcheck tests/test_scratchpad_spawn_live.sh` → no new findings compared
  with the pre-edit file.
- `bash -n tests/test_scratchpad_spawn_live.sh`.
- The post-phase equivalence check above.
- **The live test itself (`bash tests/test_scratchpad_spawn_live.sh`) must run in
  a terminal that is not inside tmux, with no `-L ait` server alive.**
  `require_clean_ait_server` refuses to run inside tmux, and the user's `ait`
  server is up. Its `pane-died` cleanup hooks run raw `tmux`, so forcing it here
  is unsafe. The run is offered as a manual-verification follow-up at Step 8c.

Step 9 (Post-Implementation): current-branch mode, so there is no merge. Archive
via `aitask_archive.sh 2121`.

## Risk

### Code-health risk: low
None identified. The change is test-only, two hunks in one file, and follows the
t2079 precedent.

### Goal-achievement risk: low
- The live test cannot be run from this agent session (inside tmux, with a real
  `-L ait` server). So the claim that `enter_scratch_cwd` does not change its
  behaviour rests on a static cwd audit, not on an execution. · severity: low
  (residual — the key_for rewrite is addressed by inline post-phase
  keyfor_standalone_equivalence; the full live run is still a manual step) ·
  → mitigation: inline post-phase keyfor_standalone_equivalence

### Planned mitigations
- timing: post-phase | name: keyfor_standalone_equivalence | type: test | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: goal-achievement: live test not runnable in the agent session | desc: run the rewritten key_for standalone from the scratch cwd against the real store helper; assert output byte-identical to the old form, and that a bad root gives exit 1 with empty output

## Final Implementation Notes
- **Actual work done:** None in this task. The remote drift check at the
  Checkpoint found that `origin/main` commit 5211159fc50a (t2095, "Fix macOS-red
  tests found by the wc -l sweep") already carried exactly the two changes this
  plan describes, in `tests/test_scratchpad_spawn_live.sh`: the `enter_scratch_cwd`
  block after `PROJECT_DIR=`, and the `(cd "$1" || exit 1` rewrite of `key_for()`.
  The user merged remote `main`. The task was then closed as already fixed by t2095,
  with no code commit.
- **Deviations from plan:** The implementation steps were not performed by this
  task. t2095 made them upstream. Verification was run against the merged tree
  (HEAD 931f2fa6d919).
- **Verification (on the merged tree):**
  - `bash tests/test_cd_guard_lint.sh`: exit 0, `Results: 92 passed, 0 failed`.
    Before the merge it was 90/2.
  - `bash -n tests/test_scratchpad_spawn_live.sh`: OK.
  - `shellcheck`: no findings attributable to the fix. Remaining findings are
    SC2034 unused vars (REAL_PATH, REAL_TMUX, FAKE_AGENT, SESSIONS_SH) and
    SC1091 infos.
  - Post-phase keyfor_standalone_equivalence: all 5 checks PASS (script below,
    run as `bash keyfor_equiv.sh <repo>`). It compares the old and the shipped
    key_for from the read-only scratch cwd, against the real store helper.
  - The live test `tests/test_scratchpad_spawn_live.sh` itself was NOT run. It
    refuses inside tmux while a `-L ait` server is alive, so it must be run from a
    non-tmux terminal.
- **Issues encountered:** None beyond the duplicate.
- **Key decisions:** Close as already fixed rather than re-commit an identical diff.
- **Upstream defects identified:** None

### keyfor_standalone_equivalence script (verbatim)
```bash
#!/usr/bin/env bash
# keyfor_standalone_equivalence (t2121 post-phase): old vs new key_for, run from
# the read-only scratch cwd against the real store helper.
set -uo pipefail
PROJECT_DIR="$1"
. "$PROJECT_DIR/tests/lib/scratch_cwd.sh"
enter_scratch_cwd
STORE_SH="$PROJECT_DIR/.aitask-scripts/aitask_scratchpad_store.sh"
PAD="$(mktemp -d)/pad"

old_key_for() {
    (cd "$1" && if [ -n "${3:-}" ]; then AITASK_SCRATCHPAD_DIR="$3" "$STORE_SH" path "$2"
              else env -u AITASK_SCRATCHPAD_DIR "$STORE_SH" path "$2"; fi)
}
# Extract the shipped key_for verbatim from the test file.
eval "$(sed -n '/^key_for() {/,/^}/p' "$PROJECT_DIR/tests/test_scratchpad_spawn_live.sh")"

fail=0
check() {
    local label="$1" a b; shift
    a="$(old_key_for "$@")"; b="$(key_for "$@")"
    if [ -n "$a" ] && [ "$a" = "$b" ]; then echo "PASS: $label -> $b"
    else echo "FAIL: $label old='$a' new='$b'"; fail=1; fi
}
echo "cwd: $(pwd)"
check "with pad dir" "$PROJECT_DIR" 2101 "$PAD"
check "empty third arg" "$PROJECT_DIR" 2101 ""
check "two args" "$PROJECT_DIR" 2101

out="$(key_for /nonexistent/ait_root 2101 "$PAD" 2>/dev/null)"; rc=$?
if [ "$rc" = 1 ] && [ -z "$out" ]; then echo "PASS: bad root -> rc=1, empty output"
else echo "FAIL: bad root rc=$rc out='$out'"; fail=1; fi
[ "$(pwd)" = "${TMPDIR:-/tmp}/ait-test-cwd-$(id -u)" ] && echo "PASS: caller cwd unchanged" || { echo "FAIL: cwd moved"; fail=1; }
exit "$fail"
```
