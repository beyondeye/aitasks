---
Task: t1725_1_abort_conflicted_pull_rebase_in_task_utils.md
Parent Task: aitasks/t1725_sync_deferrals_actionable_and_safe_to_continue.md
Sibling Tasks: aitasks/t1725/t1725_2_refuse_task_data_writes_on_wedged_worktree_and_create_id_bur.md, aitasks/t1725/t1725_3_sweep_per_file_deferral_record_tree_state_gate_and_wire.md, aitasks/t1725/t1725_4_resolve_holder_pane_and_prompt_state.md, aitasks/t1725/t1725_5_syncer_and_board_deferral_screen_with_commit_on_behalf.md, aitasks/t1725/t1725_6_document_actionable_sync_deferrals.md, aitasks/t1725/t1725_7_manual_verification_sync_deferrals_actionable_and_safe_to_co.md
Base branch: main
Output branch: main
plan_verified:
  - claudecode/opus5 @ 2026-09-08 12:07
---

# t1725_1 — abort a conflicted `pull --rebase` in `_task_pull_rebase`

Parent plan: `aiplans/p1725_sync_deferrals_actionable_and_safe_to_continue.md`,
"Child 1". Finding 5 / AC3. No sibling dependency.

**Scope:** `.aitask-scripts/lib/task_utils.sh` only, plus its tests and one
header comment in `aitask_pick_own.sh`. Review surfaced several adjacent defects
(the `./ait git` gateway, merge-mode pulls, the crew worktrees, `aitask_sync.sh`'s
retry path); they are **real and recorded**, but fixing them here would turn a
contained bug fix into a framework-wide change that overlaps t1725_3's area. They
are deferred to named follow-ups — see "Deferred, with owners".

## Context

`_task_pull_rebase()` (`.aitask-scripts/lib/task_utils.sh:786`) is a bare
`_ait_data_git pull --rebase --quiet`. `task_sync()` (:606 — `aitask_pick_own.sh`
at every pick, in `--sync` mode, and the Step 7 ownership guard) and
`task_push()`'s retry loop (:746, after every claim) both call it.
`aitask_sync.sh:do_pull_rebase` already aborts on conflict; this is the one
framework path that does not.

On 2026-09-07 it hit a trivial frontmatter conflict one second after t1717
committed `plan_approved`, stopped mid-rebase with 13 picks remaining, and from
then on every `./ait git` write in that agent died in
`assert_data_worktree_clean` ("stuck mid-rebase-merge"); the agent fell back to
plain git on `main`.

The cleanup must be **symmetric**: clean up the rebase *this call* started, and
never touch one it did not. The data worktree is shared by concurrent sessions on
the host — which is exactly the incident shape — so "a rebase exists now and did
not before" is not ownership evidence on its own.

## Verified against the current tree

Line references resolve (`_task_pull_rebase` 786, `task_sync` 606, `task_push`
714/746, `_task_push_classify` 828, `_task_push_reason_hint` 865,
`assert_data_worktree_clean` 291). Four corrections to the pre-existing plan:

1. **The wedge helper already half-exists.** t1704 added
   `ait_data_inprogress_state()` (:226) — first match over
   `AIT_GIT_INPROGRESS_STATES` under `_ait_data_gitdir`, empty when clean, always
   returns 0. A second copy of that loop is the duplication CLAUDE.md forbids.
   What it deliberately lacks is the **legacy fallback**: in legacy mode
   `_ait_data_gitdir` answers empty by contract, so it can never see a wedge —
   and legacy mode is where `_ait_data_git` runs `git` in the code repo. The new
   helper is the legacy-aware sibling; the loop is shared, not copied.

2. **`orig-head` is the ownership signal, and it exists.** Confirmed on git
   2.55.0: after a conflicted `pull --rebase`, `<gitdir>/rebase-merge/orig-head`
   holds exactly the pre-pull HEAD, and `rebase-apply/orig-head` exists for the
   apply backend too.

3. **A non-rebase state must not get rebase wording or a rebase remedy.**
   `_data_wedge_state` reports all six `AIT_GIT_INPROGRESS_STATES` because
   sibling t1725_2 needs them. Verified reachable: with `MERGE_HEAD` present,
   `git pull --rebase` fails with `error: Pulling is not possible because you
   have unmerged files.` and creates no rebase state — text that matches no
   current classifier arm (`*CONFLICT*` is case-sensitive), so it lands on
   `unknown` today.

4. **The abort must be verified, not assumed.** `rebase --abort … || true`
   swallows its own failure, and the new `rebase_conflict` hint claims "aborted
   (nothing left in progress)" — false if it did not land.

Not a problem, checked: `task_data_converge` calls `_task_push_classify` three
times (:970, :1002, :1017) always with `rebase_err=""`, so `rebase_conflict` has
exactly two producers — `task_sync` and `task_push`, both via `_task_pull_rebase`.
Changing that hint cannot mislead a converge caller.

## Steps

### Pre-phase (risk mitigation)

1. [characterize_wedge_guard] Before editing `assert_data_worktree_clean`, run
   `bash tests/test_task_git.sh` and record Test 16's verdict (the six-state
   matrix with its per-state negative controls) as the pre-refactor baseline;
   re-run after step 1 and require an identical verdict.

### Main implementation — all in `lib/task_utils.sh`

1. **Shared wedge-state helpers** (the piece t1725_2 depends on):
   - `_ait_inprogress_state_at <gitdir>` — first `AIT_GIT_INPROGRESS_STATES`
     member present under `<gitdir>`, nothing when clean or `<gitdir>` empty;
     always returns 0.
   - `ait_data_inprogress_state()` delegates to it (contract unchanged: empty in
     legacy mode).
   - `assert_data_worktree_clean` delegates to it too — its loop is
     byte-equivalent, so this is pure de-duplication, guarded by the pre-phase
     baseline. **No other change to that function's behaviour.**
   - `_data_wedge_gitdir()` — resolves by **mode**, not by emptiness:
     `ait_data_mode` = `legacy` → `git rev-parse --git-dir`, else
     `_ait_data_gitdir`. Never fall back to the code repo's git-dir in branch
     mode.
   - `_data_wedge_state()` = `_ait_inprogress_state_at "$(_data_wedge_gitdir)"`,
     reporting all six states (t1725_2's message is "mid-\<state\>").

2. **A narrowly scoped data-worktree pull mutex.** Serializing is required
   because the incident is same-PC concurrent sessions and `orig-head` alone
   cannot separate two pulls from an identical HEAD. It is an **adapter over the
   framework's existing mutex**, not a new protocol: `lib/stale_lock.sh` already
   provides `.gc`-guarded single-winner reclaim, never displaces a live PID, and
   releases by owner token, and `lib/registry_lock.sh`'s header names *the data
   worktree* as an intended lock location.
   - `ait_pull_mutex_acquire [timeout=10]` / `ait_pull_mutex_release` over
     `stale_lock_acquire` / `stale_lock_release`, lock dir
     `<_data_wedge_gitdir>/aitask-pull.lock`, token in a **private** slot.
   - **Not** `registry_lock.sh`: it keeps one lock per process in a single slot
     and installs its own `EXIT` trap; `aitask_sync.sh` already holds one
     (:573-591), so a second acquire would overwrite the slot and lose that
     release.
   - Acquired and released **only inside `_task_pull_rebase`**, which has a
     single exit point — no traps, no cross-file lock lifetime, nothing for
     another script to leak.
   - Never call it inside `$( )` — `stale_lock.sh:75` documents that
     `STALE_LOCK_TOKEN` is lost across a command substitution.
   - **State the guarantee honestly in the comment:** this serializes
     `_task_pull_rebase` against other `_task_pull_rebase` calls — the pick-time
     and push-retry pulls, which are by far the most frequent. It does **not**
     cover `aitask_sync.sh`, the `./ait git` gateway, or raw `git`; those are
     deferred (below), and for them the ownership gate still fails closed.

3. **`ait_rebase_abort_if_ours <runner> <gitdir> <head_before> <state>`** — the
   ownership gate. Prints one token, always returns 0:
   - state not `rebase-merge` / `rebase-apply` → `not_ours`, nothing touched;
   - `<gitdir>/<state>/orig-head` missing, unreadable, or ≠ `<head_before>` →
     `not_ours`, nothing touched;
   - otherwise abort, then **re-read** `_ait_inprogress_state_at <gitdir>`: still
     non-empty → `abort_failed`, empty → `aborted`.

4. **`_task_pull_rebase` — serialize, pull, prove, abort.** Single exit point.
   It captures the pull's own output and re-emits it on stderr before any
   sentinel, so `pull_err` / `rebase_err` are unchanged for the classifier; the
   pull's exit status is returned unchanged whenever a pull ran.

   ```
   ait_pull_mutex_acquire || { >&2 "<pull_locked sentinel>"; return 1; }
   before="$(_data_wedge_state)"
   head_before="$(git --git-dir="$(_data_wedge_gitdir)" rev-parse HEAD 2>/dev/null || true)"
   out="$(_ait_data_git pull --rebase --quiet 2>&1)" || rc=$?
   … decide …
   ait_pull_mutex_release
   return $rc
   ```

   Failing to acquire means **no pull is attempted** — nothing reconciled,
   nothing destroyed. Ownership signals, in order; any miss leaves the worktree
   untouched:

   1. `before` empty. Otherwise emit the state-specific pre-existing sentinel
      (step 5) and return.
   2. `after="$(_data_wedge_state)"` non-empty; if empty the pull failed without
      wedging anything (e.g. `dirty_worktree`).
   3. The pull's own output is conflict-shaped (`CONFLICT`, `could not apply`,
      `Resolve all conflicts`) — a pull that refused before fetching cannot have
      created the rebase we are looking at.
   4. **`after` is a rebase state.** If not (a merge-mode conflict leaving
      `MERGE_HEAD`), emit the `mid-<state>` sentinel and return. Without this
      branch the flow reaches signal 5, whose `not_ours` sentinel says *rebase*
      and would hand a merge conflict `rebase --abort`.
   5. `ait_rebase_abort_if_ours` — `orig-head` must equal `head_before`.

   Sentinels, each mapping to exactly one reason code. **No sentinel names a
   rebase unless the state is one:**
   - `aitask: rebase aborted after conflict - worktree restored, local commits kept` → `rebase_conflict`
   - `aitask: rebase --abort failed - a rebase is still in progress in the data worktree` → `rebase_in_progress`
   - `aitask: a rebase started outside this pull is in progress in the data worktree - leaving it untouched` → `rebase_in_progress`
   - `aitask: a rebase appeared in the data worktree during a pull that failed for another reason - leaving it untouched` → `rebase_in_progress`
   - `aitask: the data worktree is mid-<state>; leaving it untouched` → `data_midop`
   - `aitask: another session is reconciling the task data right now; pull skipped` → `pull_locked`

   Comment the residual: with the mutex covering only this function, a
   concurrent `ait sync` or a raw `git` can still start a rebase inside the
   window. Signals 1-4 fail closed for every such case except an identical
   starting HEAD, and `rebase --abort` restores `orig-head`, so committed work is
   never at stake — the exposure is conflict-resolution progress. Closing it
   fully needs the sync-side change deferred to t1725_3's area.

5. **State-specific pre-existing sentinel** (signal 1's else-branch):
   `before` ∈ {`rebase-merge`, `rebase-apply`} →
   `aitask: a rebase is already in progress in the data worktree (<state>)`;
   otherwise → `aitask: the data worktree is mid-<state>; leaving it untouched`.

6. **`_task_push_classify` — three new arms, all before the CONFLICT arm**
   (patterns disjoint): `*"reconciling the task data right now"*` →
   `pull_locked` (first — no pull was attempted); `*"in progress in the data
   worktree"*` or `*"appeared in the data worktree during a pull that failed"*` →
   `rebase_in_progress`; `*"the data worktree is mid-"*` → `data_midop`. Git's
   own `"rebase-merge directory"` / `"rebase-apply"` texts stay on
   `rebase_conflict`; when a wedge pre-exists both are present and the earlier arm
   wins, which is also what `task_push`'s accumulated `rebase_err` needs.

7. **`_task_push_reason_hint` — one changed arm, three new:**
   - `rebase_conflict` → `rebase hit conflicts and was aborted (nothing left in progress); local and remote diverge — reconcile with 'ait syncer' or './ait sync'`
   - `rebase_in_progress` → `a rebase is in progress in the data worktree; './ait git rebase --abort' discards only the partially replayed remote commits (your committed work stays on the branch), or resolve and './ait git rebase --continue'`
   - `data_midop` → `the data worktree is mid-operation (merge, cherry-pick, revert or bisect); run './ait git-health' for the exact state, then finish it or abort it with the matching './ait git <op> --abort'`
   - `pull_locked` → `another session is reconciling the task data right now; nothing was changed — retry in a moment, or run './ait git-health' if it persists`
   - `assert_data_worktree_clean`'s die text gains the same one-line "what
     `--abort` discards" sentence next to its `rebase --abort` line.

8. **`_task_sync_warn` (:684)** — extend the case to
   `dirty_worktree|rebase_conflict|rebase_in_progress|data_midop|pull_locked`,
   or a wedge with nothing pending warns nothing at all.

9. **`aitask_pick_own.sh:35-37`** — add the three codes to the
   `SYNC_FAILED:<reason>` header comment. That is the code's own contract, not
   user-facing documentation.

10. `shellcheck .aitask-scripts/lib/task_utils.sh`.

## Verification

`tests/test_task_push.sh` — Test 19 already builds the exact forced conflict
(local commit vs. a second clone editing the same line) and runs in **legacy**
mode (`_AIT_DATA_WORKTREE="."`), which is what exercises `_data_wedge_gitdir`'s
legacy fallback. Extend rather than duplicate.

**Conflict cleanup + the AC3 clause.** Test 19's trailing
`git rebase --abort || true` ("leave the fixture recoverable") becomes the
contract: after `task_sync` — rc 0, `TASK_SYNC_STATUS=failed`,
`TASK_SYNC_REASON=rebase_conflict`, **no `rebase-merge` / `rebase-apply` under the
git-dir**, stderr carries `worktree restored`, and **a subsequent `task_git
commit` of a new file succeeds**. Re-pin its `rebase --abort` warning assertion
to the new hint text. Repeat through `task_push`'s retry loop in branch mode
(`setup_branch_mode`), covering the other git-dir resolution path, and
end-to-end via `aitask_pick_own.sh --sync` → `SYNC_FAILED:rebase_conflict`, no
wedge.

**Pre-existing wedges are never touched.**
- planted `rebase-merge` with a foreign `orig-head` (the shape
  `tests/test_task_git.sh:812-820` uses) → still present, reason
  `rebase_in_progress`, stderr says `already in progress`;
- planted `MERGE_HEAD` → still present, reason **`data_midop`**, the message
  names `MERGE_HEAD`, and neither sentinel nor hint contains `rebase`. Assert the
  reason and the absence of rebase advice, not merely that `MERGE_HEAD` survived
  — surviving is also what the wrong design did;
- a pull failing on a dirty worktree with `rebase-merge` planted mid-test → left
  in place, no abort attempted.

**Failed aborts** — the branch a real conflict never exercises. After
`reload_task_utils`, override the runner:
`_ait_data_git() { [[ "$1" == rebase && "$2" == --abort ]] && return 1; LC_ALL=C git "$@"; }`,
then run the same forced conflict through `task_sync`. Assert: the wedge is
**still present**, reason `rebase_in_progress`, stderr contains `rebase --abort
failed`, and stderr does **NOT** contain `worktree restored`. The conflict-cleanup
case above is its negative control — same fixture, real runner, opposite verdict
on all four. Restore with `reload_task_utils`.

**Ownership gate, unit level** (`ait_rebase_abort_if_ours` against a fabricated
git-dir and a stub runner, so every branch is deterministic):
matching `orig-head` + stub removes the dir → `aborted`; matching + stub returns
1 and leaves it → `abort_failed`; mismatched SHA → `not_ours` **and the stub
records it was never invoked**; `orig-head` absent → `not_ours`, never invoked;
state `MERGE_HEAD` → `not_ours`, never invoked.

**Mutex, scoped to what this task actually claims.**
- a second process holding `<gitdir>/aitask-pull.lock` while a conflicted
  `task_sync` runs → `TASK_SYNC_REASON=pull_locked`, **no rebase started**, the
  holder's state untouched;
- release the holder and re-run → the pull proceeds (the control proving it was
  the lock, not a broken fixture);
- dead-holder reclaim: a lock naming a definitively absent pid → acquired;
- live holder never displaced: a lock naming this test's own live pid → busy for
  the whole timeout, lock intact;
- **release on every path**: after each of the conflict / dirty / success /
  failed-abort cases, the lock dir is gone — and after the busy case, the run
  that failed to acquire left no lock either.

**Classifier and hints.** Fixture rows for each new sentinel, including the
ordering rows where a conflict sentinel co-occurs with an in-progress sentinel
(`rebase_in_progress` wins) and with a `pull_locked` sentinel (`pull_locked`
wins). All four hint strings pinned verbatim (`:361` updated, three added).

Every "no wedge afterwards" assertion is paired with a clean-worktree control, so
it cannot pass because the fixture never wedged.

Run: `bash tests/test_task_push.sh`, `bash tests/test_task_git.sh`,
`shellcheck .aitask-scripts/lib/task_utils.sh`.

## Deferred, with owners

Each is a real defect found while verifying this plan, recorded so it is not
lost. Create the follow-ups at Step 8d and send the notes at Step 8.

| finding | disposition |
|---|---|
| `./ait git pull --rebase` (`ait:333-345` → `task_git`) leaves a wedge on conflict; routing it needs a git **global-option parser**, since `-c pull.rebase=false pull` defeats a `$1 == pull` test | **new follow-up task** — gateway pull policy + `ait_git_subcmd_index` |
| `_ait_git_subcmd_is_readonly` (:253) / `_ait_git_subcmd_is_recovery` (:274) key on `${1:-}`, so **`./ait git -c core.pager=cat rebase --abort` — the recovery command the die message advertises — is refused today** | same follow-up (it is the same parser) |
| merge-mode gateway pulls leaving `MERGE_HEAD`; needs its own `ORIG_HEAD` ownership evidence | same follow-up, stated as its own bound |
| crew worktrees: `aitask_crew_setmode.sh:125` / `addwork.sh:328` abort unconditionally, and there is **no lock anywhere in the crew family** while `brainstorm_session.py` drives both programmatically | **new follow-up task** |
| `aitask_sync.sh:1198` (do_push retry) leaks a wedge on conflict; `do_pull_rebase`'s `exit 0` at :1037/:1069 would leak any lock held across it; whole-window serialization of the resolution loop | **note to t1725_3**, which owns that file — do not restructure it here |
| the website's `FAILED:<reason>` table (`sync.md:199`) and prose (:181) list a closed reason set that this task extends by three | **note to t1725_6**, which owns user-facing docs |
| `DEFERRED_REASONS` (`sync_action_runner.py:73-77`) is a closed three-member set that fails closed on an unknown reason, so `pull_locked` cannot be a deferral token | **note to t1725_3 / t1725_5**, who own the deferral protocol |

## Coordination

Sibling **t1725_2** expects `_data_wedge_state()` with this name and contract and
will add it itself if this task has not landed. This task lands it first;
t1725_2 must be told it exists, that it delegates to a shared loop with
`ait_data_inprogress_state`, and that `_data_wedge_gitdir()` is available for its
own git-dir resolution. `ait note` at Step 8, alongside the notes above.

## Risk

### Code-health risk: medium
- `assert_data_worktree_clean` is the guard behind every `./ait git` write; delegating
  its loop to a shared helper touches a load-bearing path even though the semantics are
  byte-equivalent · severity: medium · → mitigation: inline pre-phase characterize_wedge_guard
- `_task_pull_rebase` mutates (`rebase --abort`) in a shared worktree. The mutex plus the
  five-signal gate closes the `_task_pull_rebase`-vs-`_task_pull_rebase` case, which is the
  incident shape; a concurrent `ait sync` or raw `git` from an identical HEAD remains,
  bounded to conflict-resolution progress since `--abort` restores `orig-head`
  · severity: medium · → mitigation: addressed inline in steps 2-4 (mutex + fail-closed gate + a comment stating the exact bound), with the remainder deferred to t1725_3's area
- Three new reason codes enter a set the website documents as closed, and this task
  deliberately does not update those docs · severity: low ·
  → mitigation: addressed inline in step 9 (the code-side header comment) plus the note to t1725_6, which owns the doc surface
- A first-ever lock on the data worktree: a leaked lock would make every later pull report
  `pull_locked` · severity: low · → mitigation: addressed inline in step 2 (single-exit-point acquire/release inside one function, no traps) and pinned by the release-on-every-path assertions

### Goal-achievement risk: low
- AC3 says "the task's next `./ait git commit` succeeds" — true only if the abort actually
  lands, which is why step 3 re-reads the state and the tests force the failure branch with
  a stub runner · severity: low · → mitigation: none (the forced-failure test and its control)
- Failing closed on unproven ownership leaves a genuinely-ours rebase behind when its
  `orig-head` cannot be read — the pre-fix behaviour, never worse · severity: low ·
  → mitigation: none (the `abort_failed` / `not_ours` sentinels make it visible rather than silent)
- The deferred gateway/crew/sync paths still leave wedges after this lands, so the parent's
  "any framework-driven pull" wording is not yet fully met · severity: low ·
  → mitigation: none — recorded explicitly in "Deferred, with owners" with named follow-ups, rather than implied as covered

### Planned mitigations
- timing: pre-phase | name: characterize_wedge_guard | type: test | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: code-health — delegating assert_data_worktree_clean's loop | desc: capture tests/test_task_git.sh Test 16's six-state verdict as a pre-refactor baseline and require it unchanged after
- timing: after | name: gateway_pull_policy | type: bug | priority: medium | effort: medium | inline_risk: high | added_complexity: high | addresses: goal — ./ait git pull leaves a wedge, and the argv parser it needs also fixes the refused `-c … rebase --abort` recovery | desc: add ait_git_subcmd_index, route gateway pulls through the guarded cleanup, retrofit the two subcommand classifiers, and state the merge-mode bound
- timing: after | name: crew_pull_cleanup | type: bug | priority: medium | effort: medium | inline_risk: medium | added_complexity: medium | addresses: goal — crew worktrees abort unconditionally with no serialization | desc: apply the ownership-checked cleanup and a per-gitdir lock to the two crew pull sites
