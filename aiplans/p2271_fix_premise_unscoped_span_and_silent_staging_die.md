---
Task: t2271_fix_premise_unscoped_span_and_silent_staging_die.md
Base branch: main
Output branch: main
plan_verified: []
---

# t2271 — Fix premise-staleness unparseable span and silent staging die

## Context

Two pre-existing defects, both surfaced while verifying t2261_1:

1. `tests/test_no_unscoped_task_commit.sh` fails (102/1) on
   `.claude/skills/task-workflow/premise-staleness.md:213` with
   `AIT_UNPARSEABLE_SPAN`. **Root cause (measured):** the instruction is already
   scoped (`aitask_task_commit.sh -m "…" <task_file>`), but its inline code span
   opens on line 212 and closes on line 213. The scanner (`MD_JOIN_AWK`) works
   per line: line 213 then has an odd number of backticks (the orphaned close
   plus the balanced `` `./ait git push` ``) and matches `` `[^`]*git[ \t] ``.
   So it keeps joining the following lines, whose backticks are all balanced
   and can never fix the parity, until its 4-join cap trips and it emits the
   sentinel.
2. `ait_commit_paths_staging_untracked` (`.aitask-scripts/lib/task_utils.sh`)
   runs `task_git add -- "$p" >/dev/null 2>&1`. The up-front
   `assert_data_worktree_clean commit` pre-flight only catches a worktree that
   is already wedged. If the worktree wedges mid-loop (after the pre-flight),
   `task_git`'s own guard `die()`s inside the redirected `add`: the process
   exits 1 and prints nothing. git's own `add` failures (index.lock, ignored
   path) are discarded the same way.

**Related pre-existing defect, deferred (found in plan review, verified):** the
cleanup `ait_unstage_staged_by_us` runs `task_git reset`, and `reset` is
neither readonly nor a recovery subcommand
(`_ait_git_subcmd_is_readonly` / `_ait_git_subcmd_is_recovery`). After a
mid-loop wedge, the guard therefore dies inside the cleanup, and paths an
earlier iteration staged stay in the shared index. Fixing this safely is **not**
possible from index state alone: while an operation is in progress, an entry we
staged can also belong to it. A user-measured case is a new file with
identical content added by the incoming branch of a stopped
`git merge --autostash`. It is stage-0, absent from HEAD and not unmerged, yet
it is MERGE_HEAD's, and even the blob OID is identical. Removing it would
corrupt the pending merge. So this task **preserves** that state and makes it
visible; a correct unwind needs ownership or serialization evidence and goes
to a follow-up task.

Intended outcome:
- the scanner test is green;
- every caller of the helper gets the guard's message (and git's add error)
  on stderr;
- a mid-loop wedge leaves no capture file behind;
- any owned path left staged is **named** on stderr instead of vanishing
  silently, through every real caller, including the release ledger's
  wrappers, which today discard the cleanup's streams. No unknown operation
  state is modified.

Working on current branch (`main`), profile `fast`.

## Implementation

1. **`.aitask-scripts/lib/task_utils.sh` — `ait_commit_paths_staging_untracked`**
   (mirror the existing `task_git_commit_scoped` / `_ait_cs_errf` pattern in
   the same file):
   - In the loop, after the `ls-files` probe and before the redirected `add`,
     call `assert_data_worktree_clean add -- "$p"` in the current shell, so a
     wedge that appeared mid-loop dies with its message on terminal stderr.
     (`die` is `exit 1`, so capture-and-re-emit cannot carry it. That is the
     same reason `task_git_commit_scoped` pre-asserts.) Paths staged by
     earlier iterations are handled by step 1b (named, not reset).
   - Allocate the capture file **lazily, after that assert** (first add only)
     into a global `AIT_STAGE_UNTRACKED_ERRF`, so a die at the assert leaves no
     file. On mktemp failure, degrade to `/dev/null`.
     `task_git add -- "$p" >/dev/null 2>"$sink"`. On failure: re-emit the file
     to stderr, then the existing unstage + `return 1`. On success: truncate it
     (warnings stay silent, as before). Remove it after the loop.
   - (Partly drafted before this plan; it is revised to the above.)

1b. **`ait_unstage_staged_by_us` — make the wedged case visible, change nothing
   in it:**
   - First, remove `AIT_STAGE_UNTRACKED_ERRF` if set, before the early return.
     Every caller's existing EXIT trap then also covers the capture file on an
     abnormal exit, with no change to callers' traps.
   - If `ait_data_inprogress_state` is empty, **or** the caller explicitly set
     `AIT_GIT_SKIP_STATE_CHECK=1` (e.g. `aitask_metadata_commit.sh`'s
     preflight), behaviour is unchanged (`task_git reset -q -- <owned>`). An
     explicit bypass keeps its current meaning.
   - Otherwise, if it reports a wedge: **do not reset** (no guard bypass). `warn` once:
     these owned paths may still be staged in the data index; they were left
     untouched because an in-progress `<state>` may own their entries; once the
     operation is resolved, check `./ait git status` and unstage any that are
     still ours with `./ait git reset -q -- <paths>`. Then clear the list. This
     replaces today's silent die-inside-cleanup with an explicit, fail-safe
     limitation. (Side effect: a composed handler such as
     `aitask_create_manual_verification.sh`'s `mv_create_cleanup` now also
     reaches its `rm -f "$tmp_desc"` instead of dying before it.)

1c. **Warning delivery through suppressing callers — `.aitask-scripts/lib/release_issue_ledger.sh`**
   (verified: an audit of every `ait_unstage_staged_by_us` call site shows
   these two are the only ones that discard streams). `_ril_record_cleanup`
   (~L331) and `_ril_move_cleanup` (~L640) run
   `( ait_unstage_staged_by_us ) >/dev/null 2>&1 || true`. Change both to
   `( ait_unstage_staged_by_us ) >/dev/null || true`:
   - keep the subshell and `|| true`, so a late die (e.g. the microsecond race
     inside `task_git`) still cannot pre-empt the lock release that follows;
   - keep stdout suppressed, because the ledger's stdout is its one result-line
     channel;
   - let stderr through.
   Update the "Nested:" comment: the cleanup now refuses rather than dies on a
   wedge, and the nesting remains as lock-release isolation. In the
   non-wedged case nothing new reaches stderr, because the helper's own reset
   is already `>/dev/null 2>&1`.
2. **`.claude/skills/task-workflow/premise-staleness.md` ~L211-216** — reflow
   the prose only, so the whole
   `` `aitask_task_commit.sh -m "ait: Revert t<task_id> to Ready (premise check)" <task_file>` ``
   span sits on one line. The wording is unchanged.
3. **Regenerate derived copies of that procedure** (all tracked, all currently
   clean):
   - Remote prerenders: `.claude/skills/task-workflow-remote-/`,
     `.agents/skills/task-workflow-remote-codex-/` and
     `.opencode/skills/task-workflow-remote-/` `premise-staleness.md`, via
     `./.aitask-scripts/aitask_skill_render.sh aitask-pickrem|aitask-pickweb --profile remote --agent claude|codex|opencode --force`.
   - Procedure golden `tests/golden/procs/task-workflow/premise-staleness-default.md`,
     using the loop in `tests/test_skill_render_task_workflow.sh`.
   - Review each diff with `git diff --stat`: only premise-staleness files
     should change, and only by the reflow.
4. **Regression tests** in `tests/test_task_commit_scoped.sh`. They source the
   fixture's copied `terminal_compat.sh` + `task_utils.sh` and call the helper
   directly, with `trap ait_unstage_staged_by_us EXIT` like the real callers
   and a scratch `TMPDIR`. The call is direct because going through
   `aitask_task_commit.sh` would trip its own classifier's `ls-files` probe
   first. A PATH `git` shim plants `MERGE_HEAD` (after running the real git)
   on the `ls-files --error-unmatch` probe of one named path.
   - **Test 9d — diagnostic (wedge before anything is staged):** one untracked
     path; the wedge is planted on its probe. Assert: non-zero exit, stderr
     contains `Data worktree (.aitask-data) is stuck mid-MERGE_HEAD`, no
     commit, and no `ait_stage_untracked_err.*` left in `TMPDIR`. This test
     pins only the diagnostic: nothing was staged, so it says nothing about
     cleanup.
   - **Test 9e — partial progress, through the real caller
     `aitask_task_commit.sh` (its own EXIT trap, real stream handling):** two
     untracked paths. The PATH shim runs the real `add` of the **first** path,
     then plants `MERGE_HEAD`. This avoids the classifier-probe ambiguity: the
     helper's next iteration hits the new explicit assert with the first path
     already staged. Assert: the guard message is on stderr;
     the cleanup warning names the first path; the first path's index entry is
     **preserved** (deliberately, not unstaged); the bystander's foreign staged
     entry is untouched; there is no commit; no capture file is left. The test
     comment names the follow-up task. When that task lands a safe unwind, this
     test's "preserved" assertion is what it flips.
   - **Caller-level, through the suppressing wrapper —
     `tests/test_issue_update_ledger.sh` new case (u):** add a shim mode
     `AIT_TEST_WEDGE_ON_ADD=1` (once-marker, like `AIT_TEST_WEDGE_ON_PROBE`). It
     runs the real `add` of the `.rec` path, then plants `MERGE_HEAD`, so the
     scoped commit's assert dies with the record staged and
     `_ril_record_cleanup` runs. Run in branch mode. Assert: the run fails;
     `$IFX_ERR` contains the cleanup warning naming the `.rec` path; the lock is
     released (the existing (s)-style check); the entry is still in the index
     (the documented limitation). Then remove `MERGE_HEAD` and unstage it, so
     later cases start clean. Pre-fix expectation: the warning assertion FAILS.
     With step 1c reverted (streams suppressed again), the warning assertion
     also FAILS: the measured mutation row for 1c.
   - Extend **Test 8** (ignored path): assert the output now carries git's own
     add reason (`ignored by one of your .gitignore files`).
   - Pre-fix control (measured, never stash): run the new assertions with the
     fixture's `task_utils.sh` replaced by
     `git show HEAD:.aitask-scripts/lib/task_utils.sh`. Expected pre-fix: 9d
     message FAILS, 9e message and warning FAIL, and the Test 8 reason FAILS.
     All pass post-fix. Record the measured rows in the header's mutation
     table.
   - Test 9d stays a direct helper call: it is the only way to wedge after the
     pre-flight with nothing staged. It is labelled diagnostic-only; the
     delivery claim rests on 9e and (u), not on 9d.
5. **`tests/test_issue_update_ledger.sh` L524-525** — the comment says the
   helper "silences the guard's own die message". Reword it to the current
   state: the hint still reads the wedge back (the assertion stays valid).
6. **Follow-up task** (created post-implementation, `followup_kind:
   upstream_defect`, anchored to t2261): "Safe unwind of owned staged paths
   after a mid-operation wedge". It records the measured merge `--autostash`
   counter-example, why index-state checks (HEAD absence, unmerged entries,
   blob OID) cannot prove ownership, and candidate directions: serializing
   staging against operations via the data-index lock, or recording an
   ownership witness at stage time. It requires a real-operation regression,
   not fabricated index entries.

## Verification

- `bash tests/test_no_unscoped_task_commit.sh` → 0 failed.
- `bash tests/test_task_commit_scoped.sh` → all pass, including 9d, 9e and the
  extended Test 8. The pre-fix control is measured as listed.
- `bash tests/test_issue_update_ledger.sh` → all pass, including the new (u)
  and the existing (s). The 1c-revert mutation is measured to fail (u).
- `bash tests/test_task_git.sh`,
  `bash tests/test_verified_update.sh` (other helper callers) → pass.
- `bash tests/test_skill_render_task_workflow.sh`,
  `./.aitask-scripts/aitask_skill_verify.sh` → pass (goldens + prerenders).
- `shellcheck .aitask-scripts/lib/task_utils.sh`.

## Step 9

Commit code (`bug: … (t2271)`) naming only the touched paths; leave the
pre-existing unrelated dirty files alone. Then archive via Step 9.

## Risk

### Code-health risk: low
- Residual window: a wedge planted between the new explicit assert and
  `task_git`'s own assert inside the `add` still dies silently, though the
  cleanup warning now names any staged paths. The window is microseconds wide
  and is the same accepted shape as `task_git_commit_scoped`.
  · severity: low · → mitigation: none (accepted, matches existing pattern)
- Deferred limitation: after a mid-loop wedge, owned paths may remain staged in
  the shared index. This is pre-existing; it is now named on stderr instead of
  silent, and no operation state is touched.
  · severity: low · → mitigation: follow-up task (step 6)
- 1c lets the ledger cleanup's stderr through. A caller that parses the
  ledger's stderr could see a new line, but only on the failure path and only
  `warn` text; stdout (the result line) is unchanged.
  · severity: low · → mitigation: none (case (s) and (u) pin the stderr content)
- The shared helper is used by about 8 callers. The change is additive: the
  extra assert is a pure check, stderr appears only on failure, and the
  non-wedged cleanup is unchanged.
  · severity: low · → mitigation: none (covered by running the caller test files)

### Goal-achievement risk: low
None identified.

## Final Implementation Notes
- **Actual work done:** as planned.
  - `lib/task_utils.sh`:
    - `ait_commit_paths_staging_untracked` runs an in-loop `assert_data_worktree_clean add -- "$p"` before the redirected `add`.
    - The add's stderr goes to a lazily allocated capture file (global `AIT_STAGE_UNTRACKED_ERRF`), re-emitted only on failure.
    - `ait_unstage_staged_by_us` removes that file first. On a wedged data worktree (and no explicit `AIT_GIT_SKIP_STATE_CHECK=1`) it no longer resets: it names the left-staged paths in one `warn`.
  - `lib/release_issue_ledger.sh`: `_ril_record_cleanup` / `_ril_move_cleanup` keep the nested subshell and drop only stdout, so the warning reaches stderr.
  - `premise-staleness.md`: the two multi-line inline spans (~L210-213) are reflowed onto single lines. The 3 remote prerenders and the procedure golden were regenerated; their diffs are byte-identical to the source's.
  - Tests:
    - `test_task_commit_scoped.sh`: 9d (diagnostic, direct call), 9e (partial progress through `aitask_task_commit.sh`), Test 8 now asserts git's add reason, plus the mutation-table rows.
    - `test_issue_update_ledger.sh`: `AIT_TEST_WEDGE_ON_ADD` shim mode and case **(s2)**, the caller-level check through the suppressing wrapper.
- **Deviations from plan:**
  - The ledger case is labelled **(s2)**, not (u): concurrent t2261_2 had already taken (u)-(w).
  - Both premise-staleness spans were reflowed, not only the `git`-bearing one, for consistency.
- **Issues encountered:**
  - **Shared-file absorption.** I edited `release_issue_ledger.sh` and `tests/test_issue_update_ledger.sh` without the pre-edit HEAD gate while live t2261_2 had uncommitted hunks in both; `_ril_move_cleanup` was its new, uncommitted function. t2261_2's whole-file commit 37ddf2fe6 therefore carries my 1c and (s2) hunks. They were verified present in HEAD (2 wrapper lines, 10 `(s2)` lines, the shim mode). The content is correct, but the attribution is under t2261_2. Between 37ddf2fe6 and this commit, HEAD's (s2) warning assertions depended on the then-uncommitted `task_utils.sh`.
  - **Mutation m1** (drop the in-loop assert) showed something extra. A die inside the redirected `add` also sends the EXIT trap's warning into the capture file, which is then deleted. So the explicit assert carries both the diagnostic and the warning; the microsecond race inside `task_git`'s own guard still loses both (accepted residual).
- **Key decisions:**
  - The cleanup defect (unwind after a mid-operation wedge) was deferred to **t2277**, after plan review. A merge `--autostash` counter-example shows that no index state (HEAD absence, `ls-files -u`, blob OID) proves ownership. So the cleanup preserves the entries and names them; it never bypasses the guard.
  - An explicit `AIT_GIT_SKIP_STATE_CHECK=1` keeps its old meaning (the reset runs).
- **Verification evidence:**
  - `test_task_commit_scoped.sh` passes 80/80. The pre-fix control (`TC_LIB_OVERRIDE=<HEAD task_utils.sh>`) fails exactly 5 assertions (Test 8 reason; 9d message; 9e message, warning text, warning path). Mutations m1/m2/m3 fail 9d+9e / 9e capture file / 9e warning, respectively.
  - `test_issue_update_ledger.sh` passes 141/141. Scratch-copy controls: the pre-fix library and the 1c-revert each fail only the 2 (s2) warning assertions.
  - Also green: `test_no_unscoped_task_commit.sh` 103/0, `test_skill_render_task_workflow.sh` 365/0, `aitask_skill_verify.sh` OK.
  - Callers green: `test_release_notify.sh` 259/0, `test_release_notify_branch_mode.sh` 39/0, `test_task_git`, `test_verified_update`, `test_metadata_commit_seam`, `test_task_data_writer_guard`, `test_create_manual_verification{,_gates}`, `test_usage_update`, `test_verification_followup{,_anchor}`, `test_skill_rerender`.
  - shellcheck: no new findings vs HEAD.
- **Upstream defects identified:**
  - `.aitask-scripts/lib/task_utils.sh:1049 — ait_unstage_staged_by_us cannot safely unwind owned staged paths once the data worktree is wedged mid-operation (already spawned as t2277)`
