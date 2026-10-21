---
Task: t2095_fix_macos_red_tests_from_wc_l_sweep.md
Base branch: main
Output branch: main
plan_verified: []
---

# t2095 — Fix the macOS-red tests found by t1751's `wc -l` sweep

## Context

t1751's sweep found pre-existing failures on macOS 15 that have nothing to do with
`wc -l` padding. All seven reproduced serially at HEAD d59026c5b during planning.
Each has its own root cause, but every fix is a small test-side edit, so this is
one task with no children. Production code does not change.

| # | File | Root cause (verified during planning) |
|---|---|---|
| 1 | `tests/test_revert_analyze_batch.sh:222-224` | BSD grep prints `Binary file (standard input) matches` to **stdout**. GNU grep ≥3.5 sends it to stderr. `wc -l` therefore counts 1 on macOS, although no ID was extracted. |
| 2 | `tests/test_task_git.sh` 13b/13c/13d/15b | `mktemp -d` returns `/var/folders/…` (a symlink). `_ait_detect_data_worktree` answers with the physical `/private/var/…`. |
| 3 | `tests/test_task_worktree_helper.sh` cases 3/5 | Same as #2, plus `$TMPDIR`'s trailing slash makes `T//t1548test…`. The helper reports git's canonical path. Case 2 already uses `pwd -P`. |
| 4 | `tests/test_scratchpad_spawn_live.sh` | Never calls `enter_scratch_cwd`, so `test_cd_guard_lint.sh` fails 2 checks. Platform-independent. |
| 5 | `tests/test_fixture_root.sh:145` | macOS `mktemp -d` with **no template** ignores `$TMPDIR` and uses `_CS_DARWIN_USER_TEMP_DIR`. The "old shape" control therefore leaks outside the probe dir, so the probe sees 0. It also leaks 3 real dirs into `/var/folders/…/T` on every macOS run. |
| 6 | `tests/test_run_project_command.sh:128` | `sed 's/.\+/set/'`: BSD sed BRE has no `\+`, so the LOG path passes through unchanged. |
| 7 | `tests/test_sync_deferral_and_quarantine.sh` Test 33 self/other | macOS has no `/proc`, so `lock_yaml_live` records `kind: ps`. `lock_holder_liveness` (`.aitask-scripts/lib/pid_anchor.sh:276`) **never** returns `alive` for a `ps` token, by design (1-second resolution). The verdict is `unknown_liveness`, and the self/other action text comes only from `live_lock`. On macOS the assertion asks for a state that cannot be reached there. |

**Scope expansion (not in the task body; same defect class as #6).** A sweep for
GNU-only BRE escapes in test seds found two more files that are red on macOS:
- `tests/test_skill_errexit_capture.sh:209`: `\(if[[:space:]]\+\)\?` gives 8 FAILs.
- `tests/test_touchpoint_count_contract.sh:146`: `\([0-9]\+\)` gives 1 FAIL.

Mode: current branch (profile `fast`), no worktree.

## Implementation steps

1. **NUL control (#1).** In `tests/test_revert_analyze_batch.sh` replace the
   count with one that counts only extracted IDs, so the binary-match notice
   is never counted on either platform:
   ```bash
   nul_b="$( cd "$fx" && git log --all --format='%B%x00' | grep -oE '\(t[0-9]+(_[0-9]+)?\)' 2>/dev/null | grep -cE '^\(t[0-9]+(_[0-9]+)?\)$' )"
   ```
   Keep `assert_eq_trim … "0"`. Add one comment line: BSD grep writes the
   binary-match notice to stdout, GNU grep to stderr, so only ID-shaped lines
   are counted. The existing `src_b` non-empty assertion stays the positive
   control: the same regex does extract IDs without the NUL.

2. **Realpath, test_task_git (#2).** Compare against the physical path on the
   expected side only; the fixture factories stay as they are. After
   `ROOT_13=…` add `ROOT_13_P="$(cd "$ROOT_13" && pwd -P)"`, and use
   `"$ROOT_13_P/.aitask-data"` as the expected value in 13b, 13c and both 13d
   resolves. Do the same for 15b with `ROOT_15_P`, or reuse the existing
   `canon_15 "$ROOT_15"`, which already returns `pwd -P`. Leave 13a/15a
   (relative `.aitask-data`) untouched. Leave every `${…#"$ROOT_15"/}` prefix
   strip untouched too, because those operate on paths built from the logical
   root.

3. **Realpath, worktree helper (#3).** In `fresh_repo()` canonicalize the root
   once:
   `root="$(mktemp -d "${TMPDIR:-/tmp}/t1548test.XXXXXX")"; root="$(cd "$root" && pwd -P)"`.
   This gives `OUTSIDE` a single slash and the physical prefix, which matches
   what git records. `ROOTS+=` cleanup still sees the same directory.

4. **cd-guard (#4).** In `tests/test_scratchpad_spawn_live.sh`, directly after
   `PROJECT_DIR=…` (line 43), follow the precedent in
   `test_monitor_shadow_spawn_live.sh:54-56`:
   ```bash
   # Start from an empty read-only dir, never the invoking one (t1826).
   . "$PROJECT_DIR/tests/lib/scratch_cwd.sh"
   enter_scratch_cwd
   ```
   Safe by inspection: every tmux pane gets `-c "$ROOT"`; `spawn_scratchpad`
   passes `cwd=str(target_root)` (`monitor_core.py:4483`); the driver's
   `PYTHONPATH` is absolute; and the only `$PWD` use is inside a pane shim,
   whose cwd is `$ROOT`.

5. **fixture_root control (#5).** In the `old)` body of `gen_suite`
   (`tests/test_fixture_root.sh:145`) give mktemp a template:
   `d="$(mktemp -d "${TMPDIR:-/tmp}/old_XXXXXX")"`. The defect it models (an
   append lost in `$( )`) is unchanged, and the leak now lands under the probe
   on both platforms. Leave the static `$ctl/*.sh` sources at 245-280 alone:
   only the guard scanner reads them, and nothing executes them.

6. **sed `\+` (#6).** In `tests/test_run_project_command.sh:128`, change
   `sed 's/.\+/set/'` to `sed 's/..*/set/'`.

7. **Holder liveness (#7).** In Test 33 of
   `tests/test_sync_deferral_and_quarantine.sh`, gate the two action assertions
   on the platform. This follows the `[ -r /proc/self/stat ]` precedent in
   `tests/test_session_hook.sh:401`:
   ```bash
   if [ -r /proc/self/stat ]; then
       assert_contains "self: and the action offers commit-on-behalf" "--commit-for-task 10" "$ROW_SELF"
   else
       # No /proc: lock_yaml_live records a `ps` token, which never proves `alive`
       # (pid_anchor.sh lock_holder_liveness) -- the row is the fail-safe one.
       assert_contains "self (no /proc): an unprovable holder is unknown_liveness" "DEFERRED_FILE:unknown_liveness|" "$ROW_SELF"
       assert_not_contains "self (no /proc): and is never offered commit-on-behalf" "--commit-for-task" "$ROW_SELF"
   fi
   ```
   Apply the same to `other` (Linux keeps `left for that session`). Add one line
   to `lock_yaml_live`'s comment in `tests/lib/sync_fixture.sh`: without `/proc`
   the lock is `unknown`, never `alive`, by design.

8. **Scope expansion: BSD-sed escapes.** Use POSIX intervals, which GNU and BSD
   both accept:
   - `tests/test_skill_errexit_capture.sh:209`:
     `\(if[[:space:]]\+\)\?` becomes `\(if[[:space:]]\{1,\}\)\{0,1\}`.
   - `tests/test_touchpoint_count_contract.sh:146`: `\([0-9]\+\)` becomes
     `\([0-9]\{1,\}\)`.
   If either file is still red afterwards for a different reason, file it as a
   follow-up and do not widen this task further.

## Verification

- Run each file serially:
  `bash tests/<f>.sh`, using `test_revert_analyze_batch`, `test_task_git`,
  `test_task_worktree_helper`, `test_cd_guard_lint`, `test_fixture_root`,
  `test_run_project_command`, `test_sync_deferral_and_quarantine`,
  `test_skill_errexit_capture` and `test_touchpoint_count_contract`. Expect exit
  0 and no `FAIL:` lines.
- Pre-fix controls. The failing runs captured during planning are the controls:
  each assertion was observed failing against the unfixed code. For #5, also
  confirm that the probe now counts 3 for the old shape and 0 for the new one.
- `bash -n tests/test_scratchpad_spawn_live.sh` and
  `shellcheck` on every edited file.
- `test_scratchpad_spawn_live.sh` itself cannot be run here: this session is
  inside tmux and `-L ait` is alive, and `require_clean_ait_server` refuses
  both. It must be run from a plain terminal (see Risk).

## Step 9

Commit the test changes with `bug: Fix macOS-red tests found by the wc -l sweep (t2095)`,
then archive per task-workflow Step 9.

## Risk

### Code-health risk: low
- #7 drops macOS coverage of the self/other action wording. That wording is unreachable on a no-`/proc` host by design, and the replacement assertions pin the fail-safe row instead. Severity: low. Mitigation: none needed.

### Goal-achievement risk: medium
- #4 cannot be executed in this session (tmux refusal), so the cwd change to `test_scratchpad_spawn_live.sh` is verified only by lint, `bash -n` and code inspection, not by a live run. Severity: medium. Mitigation: scratchpad_live_run.
- The scope-expansion files (#8) may hide a second, non-sed failure once the sed is fixed. Severity: low. Mitigation: covered by step 8's file-a-follow-up rule.

### Planned mitigations
- timing: after | name: scratchpad_live_run | type: manual_verification | priority: medium | effort: low | inline_risk: medium | added_complexity: low | addresses: #4's cwd change unverified by a live run (tmux refusal in-session) | desc: Run bash tests/test_scratchpad_spawn_live.sh from a plain terminal (not inside tmux, -L ait stopped) and confirm it passes after enter_scratch_cwd was added
