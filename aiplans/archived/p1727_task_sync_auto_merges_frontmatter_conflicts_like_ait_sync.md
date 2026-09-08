---
Task: t1727_task_sync_auto_merges_frontmatter_conflicts_like_ait_sync.md
Base branch: main
Output branch: main
plan_verified: []
---

# t1727 — `task_sync` / `task_push` auto-merge frontmatter conflicts like `ait sync`

## Context

The framework has **two** `pull --rebase` paths on the task-data branch and only
one of them can resolve a conflict.

- `aitask_sync.sh` (`ait sync`, the syncer/board `s` key) resolves frontmatter-only
  collisions without a human: on a conflicted pull it runs `try_auto_merge`
  (`aitask_sync.sh:901`) — `board/aitask_merge.py --batch --rebase` with the merge
  base taken from stage 1 of the conflicted index — advances the rebase with
  `_rebase_advance` (`:982`), and reports `AUTOMERGED`.
- `lib/task_utils.sh::_task_pull_rebase` (`:983`) — the pull that **every pick**
  runs (`task_sync`, via `aitask_pick_own.sh --sync` and the claim) and that
  **every push retry** runs (`task_push`, `ait git push`) — is a bare
  `_ait_data_git pull --rebase --quiet`. The identical `updated_at` vs
  `boardcol`/`boardidx` collision that `ait sync` merges silently just fails here.

Since t1725_1 that failure is at least *clean* — the rebase is aborted, nothing is
wedged, `SYNC_FAILED:rebase_conflict` — but it is still unresolved: the pick
proceeds against a stale data branch, and `task_push`'s three retries burn on a
conflict they cannot clear, so the claim / gate / archive commit stays unpushed.
On this repo's data branch that is the normal case, not a corner: 43 `pull
--rebase` cycles in one day across two hosts, one of which needed a manual
`rebase --continue` through a pure frontmatter collision.

**Outcome:** one auto-merge implementation, two callers. The workflow pull
resolves exactly what `ait sync` resolves, through the same driver and the same
advance/abort logic, while keeping its best-effort contract (always return 0,
outcome in the `TASK_*` globals, one `warn` on failure).

## Design

### Pre-phase (risk mitigations)

1. `[baseline_sync_automerge_before_extraction]` **Before editing any file**, run
   `bash tests/test_sync.sh` and `bash tests/test_sync_branch_mode_automerge.sh`
   on the untouched tree. Record each file's PASS/FAIL summary and the observed
   `AUTOMERGED` / `CONFLICT:` tokens into the working notes. This is the measured
   ground truth the post-extraction run is diffed against; a test already red
   here is a pre-existing failure, not extraction damage, and must be called out
   rather than absorbed.
2. `[sentinel_single_constant]` Declare the auto-merge sentinel **once**, as a
   shell constant in `lib/task_utils.sh`:

   ```bash
   # The one spelling. The emitter in _task_pull_rebase_cleanup and BOTH matchers
   # (task_sync, task_push) read this — a literal in any of the three could drift
   # and leave TASK_*_AUTOMERGED unset while the merge itself worked.
   AIT_PULL_AUTOMERGED_SENTINEL="auto-merged"$' '"task-data conflict(s) during pull"
   ```

   Emit it with the count interpolated; match it as
   `case "$pull_err" in *"$AIT_PULL_AUTOMERGED_SENTINEL"*)`. No third literal
   anywhere.
3. `[bound_automerge_loop_iterations]` Give `ait_automerge_rebase_loop` a hard
   round cap. One round = "auto-merge the current conflict set, then advance";
   entering a round past the cap emits a distinct stderr line
   (`aitask: auto-merge gave up after N rounds`) — so "the cap fired" is
   observable and its *absence* is assertable — sets `AIT_AUTOMERGE_REMAINING`
   to the still-conflicted list, and returns `1`, so the caller takes its normal
   abort path. Today's `aitask_sync.sh` loop is an unbounded `while true`; the new
   caller holds the pull mutex for the whole loop, so an unbounded loop would
   block every other session on the host indefinitely. **This is a
   deliberate, small behaviour change on the sync side too** — state it in the
   commit message.

   **The cap is a documented env seam, so a test can actually reach it**, the
   same shape as `AITASKS_LOCK_DIR`: default `50` (well above the largest replay
   observed on this data branch, 21 commits), overridable by
   `AIT_AUTOMERGE_MAX_ROUNDS`. Validate the override as a positive integer with a
   glob and **fail closed to the default** on anything else — never let a typo
   silently disable or zero the cap:

   ```bash
   _ait_automerge_max_rounds() {
       local v="${AIT_AUTOMERGE_MAX_ROUNDS:-}"
       [[ -n "$v" && "$v" != *[!0-9]* && "$v" != 0* ]] && { printf '%s' "$v"; return 0; }
       printf '50'
   }
   ```

   (`"$v" != 0*` rejects both `0` and octal-looking `010`; the class test rejects
   empty and non-numeric.) A cap that is never exercised is not a mitigation —
   verification 10 below drives it through this seam.

### 1. New library — `.aitask-scripts/lib/task_automerge.sh`

Extract the auto-merge engine out of `aitask_sync.sh` into a lib with **no
dependency on that script's globals** (`BATCH_MODE`, `iinfo_err`, `_MERGE_PYTHON`,
`_MERGE_SCRIPT`). Self-anchored via its own `BASH_SOURCE` (the `pid_anchor.sh`
idiom), Python and driver resolved lazily on first use:

```bash
_AIT_AUTOMERGE_LIB_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# _MERGE_SCRIPT = $_AIT_AUTOMERGE_LIB_DIR/../board/aitask_merge.py
# _MERGE_PYTHON = resolve_python   (cached in _AIT_RESOLVED_PYTHON already)
```

Public surface — **stdout is never a data channel**; every diagnostic goes to
stderr and every result comes back in a global, because `_task_pull_rebase`'s
callers capture it with `2>&1` and a stray stdout line would be parsed as git
output:

| Function | Contract |
|---|---|
| `ait_automerge_files <newline-list>` | Auto-merge each `aitasks/*.md` / `aiplans/*.md`; stage what resolved. `0` = all resolved. Sets `AIT_AUTOMERGE_REMAINING` (unresolved list) and `AIT_AUTOMERGE_RESOLVED` (count). |
| `ait_automerge_advance` | `rebase --continue`, falling back to `--skip` for an empty patch. Verbatim `_rebase_advance`. |
| `ait_automerge_rebase_loop` | The full loop: merge → advance → merge again for the next replayed commit. `0` = rebase completed (`AIT_AUTOMERGE_RESOLVED` = files merged); `1` = stuck (`AIT_AUTOMERGE_REMAINING` = what it could not merge); `2` = advance failed for a non-conflict reason. |
| `ait_automerge_conflict_path <repo-relative>` | Today's `_resolve_conflict_path`. |

Two deliberate changes while lifting the code:

- **git seam.** The library uses `_ait_data_git` (task_utils.sh's raw task-data
  runner) rather than `task_git` + a scoped `AIT_GIT_SKIP_STATE_CHECK=1` bypass.
  Same worktree, same argv; it retires a documented guard-bypass instead of
  carrying it into a second caller, and `LC_ALL=C` makes git's messages
  parseable. Both callers source `task_utils.sh`, so the seam is always present.
- **Diagnostics.** `iinfo_err` (BATCH_MODE-gated) becomes plain stderr writes.
  `ait sync --batch` already sends stderr nowhere the protocol reads, and the
  `--batch` stdout tokens are untouched.

Note that the library never needs a dirty-worktree defence: `git pull --rebase`
refuses **before it fetches** whenever a tracked file is modified, so reaching a
conflict at all proves the shared worktree held no other session's uncommitted
edit.

### 2. `aitask_sync.sh` — consume the library, keep every token

Source `lib/task_automerge.sh` at startup (`test_sync.sh` and
`test_sync_branch_mode_automerge.sh` copy the whole `.aitask-scripts` tree, so no
`setup_fake_aitask_repo` entry is owed). Delete `try_auto_merge`, `_rebase_advance`
and `_resolve_conflict_path`; collapse `do_pull_rebase`'s ~45-line hand-rolled
loop (`:1010`–`:1064`) into one call:

```bash
# ABSORBING CAPTURE, never a bare call: aitask_sync.sh runs `set -euo pipefail`,
# so `ait_automerge_rebase_loop; loop_rc=$?` would exit the shell on the loop's
# own documented rc 1 (unresolved) and rc 2 (advance failed) — bypassing the
# CONFLICT: token and the interactive fallback exactly when they are needed.
# `local` on its own line so the declaration's status never masks the call's.
local loop_rc=0
ait_automerge_rebase_loop || loop_rc=$?
case $loop_rc in
  0) _PULL_AUTOMERGED=true; isuccess "All conflicts auto-merged successfully"; return 0 ;;
  2) task_git rebase --abort 2>/dev/null || true
     batch_out "ERROR:rebase_continue_failed"; return 1 ;;
esac
remaining="$AIT_AUTOMERGE_REMAINING"     # rc 1 -> existing batch / interactive handling
```

**This applies to every new non-zero-returning call, in both files** — the same
`set -e` trap, four times over. None may be a bare command:

| call | required form |
|---|---|
| `ait_automerge_rebase_loop` (sync + `task_utils.sh`) | `rc=0; ait_automerge_rebase_loop \|\| rc=$?` |
| `_task_pull_rebase_cleanup` (now returns `10`) | `rc2=0; _task_pull_rebase_cleanup … \|\| rc2=$?` |
| `_ait_load_automerge` | `if _ait_load_automerge; then … fi` |
| `ait_rebase_is_ours` | `if ait_rebase_is_ours …; then … fi` |

`_task_pull_rebase_cleanup` returns `0` today and every caller treats it as
infallible, so introducing `10` without the capture would turn a *successful*
auto-merge into an aborted pick.

**Retarget the interactive fallback — it is not part of the collapsed block and
it calls two of the three deleted helpers.** `do_pull_rebase`'s manual-resolution
branch survives verbatim except for these two call sites, which must move to the
library in the same edit or a body conflict that deliberately falls through to a
human hits a missing command instead of an editor:

| site | today | after |
|---|---|---|
| `aitask_sync.sh:1088` | `$editor "$(_resolve_conflict_path "$f")"` | `$editor "$(ait_automerge_conflict_path "$f")"` |
| `aitask_sync.sh:1116` | `if ! _rebase_advance; then` | `if ! ait_automerge_advance; then` |

Grep for both old names after the edit: zero hits outside the library is the
check. `tests/test_sync_branch_mode_automerge.sh` Tests 5–8 are the fixtures that
catch a miss (an undefined `_resolve_conflict_path` yields `$editor ""`, which
fails Test 6's "every remaining file is offered and staged"), so they stay in the
regression net and must be run, not assumed.

`AUTOMERGED`, `CONFLICT:<files>`, `ERROR:rebase_continue_failed` and the
interactive `$EDITOR` loop are otherwise unchanged. The one wording change: the
inner "Auto-merged earlier commits, but new conflicts in:" notice now comes from
the library (emitted when `AIT_AUTOMERGE_RESOLVED > 0`), so the information
survives.

### 3. `lib/task_utils.sh` — resolve, then abort only what is left

**Split the ownership proof out of the abort.** `ait_rebase_abort_if_ours`
(`:931`) currently bundles signal 5 (orig-head matches the HEAD we read before
pulling) with the abort. Extract `ait_rebase_is_ours <gitdir> <head_before>
<state>` (exit 0/1) and have `ait_rebase_abort_if_ours` call it — its
`aborted` / `abort_failed` / `not_ours` contract and its unit tests are unchanged.
Auto-merging and `rebase --continue`-ing a rebase we did not start is exactly as
dangerous as aborting one, so the new path must clear the *same* gate.

**Lazy library load**, the `pid_anchor.sh::_anchor_tmux_pane_pid` pattern —
`task_utils.sh` is copied standalone into `test_task_push.sh` fixtures, so a
missing library must degrade to "no auto-merge", never break sourcing:

```bash
_ait_load_automerge() {
    declare -F ait_automerge_rebase_loop >/dev/null 2>&1 && return 0
    [[ -r "${SCRIPT_DIR}/lib/task_automerge.sh" ]] || return 1
    source "${SCRIPT_DIR}/lib/task_automerge.sh" || return 1
    declare -F ait_automerge_rebase_loop >/dev/null 2>&1
}
```

**Rework `_task_pull_rebase_cleanup` (`:1011`) into a recover-then-clean step.**
Signals 1–4 are untouched. After signal 5 proves the rebase is ours:

1. `_ait_load_automerge` → on failure fall straight through to the abort;
2. `ait_automerge_rebase_loop`;
3. rc 0 → print the sentinel and return `10`;
4. rc 1 or 2 → the existing `ait_rebase_abort_if_ours` abort and its three
   verdict messages, unchanged.

`_task_pull_rebase` maps `10` back to `rc=0` before releasing the mutex, so a
fully auto-merged pull is a **successful** pull to both callers. The mutex is held
across the whole merge — correct (it is the window that must be serialized); other
pulls meanwhile get the already-handled `pull_locked` "retry in a moment" outcome.

**Surface the fact through stderr, not a global.** Both callers invoke
`_task_pull_rebase` inside `$( … 2>&1 )`, so anything it assigns to a global dies
in the subshell. Emit one sentinel line:

```
aitask: auto-merged N task-data conflict(s) during pull - rebase completed
```

`task_sync` sets `TASK_SYNC_AUTOMERGED=1` when `$pull_err` contains it;
`task_push` sets `TASK_PUSH_AUTOMERGED=1` from its accumulated `$rebase_err`.
The sentinel is lower-case `conflict(s)` and shares no substring with any
`_task_push_classify` arm (`*CONFLICT*` is case-sensitive), so classification is
unaffected — pin that with a fixture test.

**Both flags are declared beside the existing globals and reset on entry, exactly
like `TASK_*_STATUS`.** These are process-global result fields and both functions
run more than once per shell — `aitask_pick_own.sh` calls `task_sync` at the top
of a claim and `task_push` at the end of the same process — so a flag left at `1`
by an auto-merged pull would make the *next*, ordinary sync or push report a
merge that never happened:

```bash
TASK_SYNC_AUTOMERGED=""   # 1 when this pull auto-merged conflicts; "" otherwise
TASK_PUSH_AUTOMERGED=""   # ditto for the push cycle's pull retries
```

`task_sync()` clears `TASK_SYNC_AUTOMERGED` in the same block that clears
`TASK_SYNC_STATUS` / `_REASON` / `_UNPUSHED` / `_UNPULLED`; `task_push()` clears
`TASK_PUSH_AUTOMERGED` alongside `TASK_PUSH_STATUS` / `_REASON` / `_UNPUSHED`.
Both are set only on the sentinel match, and the reset is pinned by a
sequential-call test (verification 7 below). The empty string, not `0`, is the
"did not happen" value — it matches the surrounding fields' convention.

**`task_push` retry budget** (task item 4: an auto-merged rebase is progress, not
a failed attempt). Keep `max_attempts=3`, add a bounded grant: each pull that
reported the sentinel returns one attempt, at most `_AIT_PUSH_PROGRESS_GRANTS=2`,
hard-capping the loop at 5 pushes. Bounded, terminating, and it is what lets a
two-host repo actually land the claim commit.

### 4. Surfaces

`aitask_pick_own.sh --sync` keeps printing bare **`SYNCED`** — no
`SYNCED:automerged`. That token is matched exactly by the pick skill and by three
assertions in `test_task_push.sh`, the detail is not actionable to any of them,
and the human already gets the stderr notice. `website/content/docs/commands/sync.md`
therefore needs no protocol change; add one sentence to the pick/push description
saying the workflow pull now auto-merges the same frontmatter collisions `ait sync`
does. `task_push_report` tokens are unchanged.

### Post-phase (risk mitigations)

1. `[push_grant_termination_test]` Add a fixture in `tests/test_task_push.sh`
   where the remote **keeps** re-conflicting on a task file across every retry,
   and assert that `task_push` terminates at the hard cap — at most
   `max_attempts + _AIT_PUSH_PROGRESS_GRANTS` = 5 push attempts — reporting
   `TASK_PUSH_STATUS=failed` rather than looping. Count the attempts through a
   PATH `git` shim (the argv-keyed shim shape
   `test_sync_branch_mode_automerge.sh::install_failing_add_shim` already uses),
   so the cap is asserted as a number, not inferred from the test returning.
   The grant's termination proof, not just its happy path.

## Files

| File | Change |
|---|---|
| `.aitask-scripts/lib/task_automerge.sh` | **new** — the extracted engine, incl. the `AIT_AUTOMERGE_MAX_ROUNDS` test seam |
| `.aitask-scripts/aitask_sync.sh` | source the lib; delete `try_auto_merge` / `_rebase_advance` / `_resolve_conflict_path`; collapse `do_pull_rebase`'s loop; **retarget the two interactive-fallback call sites** (`:1088`, `:1116`) |
| `.aitask-scripts/lib/task_utils.sh` | `AIT_PULL_AUTOMERGED_SENTINEL`; `ait_rebase_is_ours` split; `_ait_load_automerge`; recover-then-clean in `_task_pull_rebase_cleanup`; `TASK_SYNC_AUTOMERGED` / `TASK_PUSH_AUTOMERGED` (declared **and reset on entry** with their `TASK_*_STATUS` siblings); push progress grant |
| `tests/test_task_push.sh` | new tests (below) |
| `website/content/docs/commands/sync.md` | one prose sentence; **no** table change |

## Verification

Behavioural fixtures added to `tests/test_task_push.sh`, reusing
`setup_remote_and_clone` + `setup_branch_mode` and the two-clone conflict shape
already proven in `tests/test_sync_branch_mode_automerge.sh::setup_branch_mode_repos`
(`status` / `boardcol` on **adjacent** lines — non-adjacent edits merge textually
and never reach the driver, which `test_sync_branch_mode_automerge.sh` Test 4
already pins as its negative control):

1. **`task_sync` converges on a frontmatter-only conflict.** Local `updated_at`
   vs remote `boardcol`, identical bodies. Assert `TASK_SYNC_STATUS=synced`,
   `TASK_SYNC_AUTOMERGED=1`, **both** sides' field values present in the merged
   file, `HEAD..@{u}` and `@{u}..HEAD` both `0`, `probe_wedge` empty, and the
   sentinel on stderr.
2. **Same through `task_push`'s retry.** A local claim commit + a conflicting
   remote frontmatter commit: assert `TASK_PUSH_STATUS=pushed`,
   `TASK_PUSH_AUTOMERGED=1`, and that the remote log contains the claim commit —
   the count, not just the status, so a green run cannot mean "nothing pushed".
3. **Negative control — body conflict on a *task* file.** `aitasks/tN.md` with
   diverging bodies is the discriminating case: it enters the auto-merge branch,
   the driver answers `PARTIAL`, and the outcome must be exactly t1725_1's —
   `TASK_SYNC_STATUS=failed`, `reason=rebase_conflict`, `probe_wedge` empty,
   worktree clean, **and no sentinel on stderr**. (Existing Test 19's
   `conflict.txt` stays as the non-task-file control.)
4. **Library absent ⇒ degrade, don't break.** In a `setup_fake_aitask_repo`
   fixture (which copies neither `task_automerge.sh` nor `board/`), sourcing
   `task_utils.sh` succeeds and a frontmatter conflict fails exactly as it does
   today — this is the standalone-fixture AC.
5. **Classifier immunity.** Drive `_task_push_classify` with a blob containing
   only the sentinel and assert it does not become `rebase_conflict` /
   `rebase_in_progress`.
6. **`pick_own --sync` end to end.** Extend the Test 23 fixture to copy the whole
   `.aitask-scripts` tree (as `test_sync.sh` does) so the driver is present, and
   assert stdout is still exactly `SYNCED` after an auto-merged pull.
7. **Sequential-call reset.** In one shell: run the fixture-1 auto-merged
   `task_sync` (assert `TASK_SYNC_AUTOMERGED=1`), then run `task_sync` again on
   the now-converged repo and assert `TASK_SYNC_STATUS=up-to-date` **and**
   `TASK_SYNC_AUTOMERGED=""`. Repeat the pair for `task_push` /
   `TASK_PUSH_AUTOMERGED` (auto-merged push, then a clean push). Without the
   entry reset the second call reports a merge that never happened.
8. **Multi-round rebase — two replayed local commits.** Fixtures 1–3 give the
   loop exactly **one** conflicted rebase step, so on their own they cannot show
   that a *second* replayed commit is merged, that `AIT_AUTOMERGE_RESOLVED`
   accumulates across rounds, or that the loop terminates after repeated
   successful advances. Build a fixture that does:

   - remote (second clone) commits one change to `boardcol` in `aitasks/t1.md`;
   - local commits **two** separate commits on the same file — commit A changes
     `status`, commit B changes `labels` — with all of `status`, `boardcol` and
     `labels` on **adjacent** lines, the same overlapping-hunk trick
     `setup_branch_mode_repos` documents, so each replayed patch's context
     includes the remote-modified line and **both** replay steps conflict;
   - bodies identical throughout, so both rounds are driver-resolvable.

   Assert, after `task_sync`: `TASK_SYNC_STATUS=synced`,
   `TASK_SYNC_AUTOMERGED=1`, `@{u}..HEAD` = `2` (both local commits replayed and
   kept), all three field values present in the merged file, `probe_wedge` empty,
   and — the discriminator — the stderr sentinel reports **`2`** merged
   conflicts. A count of `1` means only one round ran and the fixture degenerated
   into fixture 1, so the count assertion is what proves the multi-round path was
   actually exercised; if it reads `1`, fix the fixture rather than the
   assertion.
9. **Round cap does not fire on a healthy replay.** Negative control for
   `bound_automerge_loop_iterations`: the fixture-8 run must converge normally,
   with no "round cap" message on stderr — a cap that trips at 2 rounds would
   otherwise pass fixture 8's abort-free assertions for the wrong reason. Assert
   the absence of the cap sentinel alongside the count.
10. **Round cap actually fires, and fails safe when it does.** The positive
    control fixture 9 cannot supply: three conflicting local commits (fixture 8's
    construction plus one more adjacent-field commit) run with
    `AIT_AUTOMERGE_MAX_ROUNDS=1`. Assert **all four** consequences, because a
    wrong comparison, a missing abort or a missing diagnostic each break a
    different one:
    - the cap diagnostic is on stderr, naming the round count;
    - `TASK_SYNC_STATUS=failed`, `TASK_SYNC_REASON=rebase_conflict`, and
      `TASK_SYNC_AUTOMERGED=""` (a partially auto-merged run that then gave up is
      **not** an auto-merge);
    - `probe_wedge` is empty — the abort ran and landed, so the shared worktree is
      not left blocked (this is the whole point of the cap);
    - all three local commits survive on the branch (`@{u}..HEAD` = `3` against
      the pre-pull upstream), i.e. the abort restored `orig-head` and discarded
      only the partial replay.

    Also assert the env seam **fails closed**: re-run with
    `AIT_AUTOMERGE_MAX_ROUNDS=abc` and with `=0` and confirm the run converges
    (default 50 in force), so a malformed override can never disable the cap.
11. **Advance-failure path (`rc 2`).** The loop's other non-zero result, which no
    natural fixture produces: install an argv-keyed PATH `git` shim — the shape
    `test_sync_branch_mode_automerge.sh::install_failing_add_shim` already uses —
    that fails `rebase --continue` **and** `rebase --skip` while leaving nothing
    unresolved. Assert `ait sync --batch` prints `ERROR:rebase_continue_failed`
    and `probe_wedge` is empty afterwards. This is the branch the `set -e`
    absorbing capture exists for: without it the shell exits before the token is
    ever printed, so the assertion is also the capture's regression test.

Regression net (must stay green — the extraction is behaviour-preserving there):

```bash
bash tests/test_task_push.sh
bash tests/test_sync.sh                          # Tests 12-15 pin AUTOMERGED
bash tests/test_sync_branch_mode_automerge.sh    # 1-3 staging honesty; 5-8 the interactive fallback
bash tests/test_task_git.sh
bash tests/test_sync_deferral_and_quarantine.sh
bash tests/test_sync_auto_commit_scoping.sh
shellcheck .aitask-scripts/aitask_sync.sh .aitask-scripts/lib/task_utils.sh \
           .aitask-scripts/lib/task_automerge.sh
cd website && python3 check_links.py --build
```

Step 9 (Post-Implementation) handles cleanup, archival and merge as usual.

## Risk

Levels below are the **reassessment** after the four inline mitigations were
folded into the plan body (three pre-phase, one post-phase).

### Code-health risk: medium
- The extraction rewrites the *only* conflict-resolution path in `ait sync`, a
  load-bearing multi-machine seam whose failure mode (a wedged shared data
  worktree) blocks every later `./ait git` write for every session on the host
  · severity: medium · → mitigation: inline pre-phase baseline_sync_automerge_before_extraction
- Switching the library's git seam from `task_git` + `AIT_GIT_SKIP_STATE_CHECK=1`
  to `_ait_data_git` is a real behavioural change on the sync side; it is
  covered by `test_sync_branch_mode_automerge.sh` Tests 2/3/7 only because their
  shim keys on argv, which the change preserves · severity: low · → mitigation: inline pre-phase baseline_sync_automerge_before_extraction
- The auto-merge now runs while the pull mutex is held, lengthening the window in
  which concurrent pulls report `pull_locked` · severity: low · → mitigation: inline pre-phase bound_automerge_loop_iterations

Held at **medium** rather than dropped to low: the baseline and the loop bound
make the change *observable* and *terminating*, but they do not narrow the blast
radius — this is still the one conflict-resolution seam every machine shares.

### Goal-achievement risk: low
- The automerge fact must travel to the callers as a stderr **sentinel** because
  `_task_pull_rebase` runs inside `$( )`; a sentinel that drifts from its matcher
  would silently leave `TASK_SYNC_AUTOMERGED` unset while the merge still worked
  · severity: low · → mitigation: inline pre-phase sentinel_single_constant
- The `task_push` progress grant adds a second termination condition to a retry
  loop; an unbounded grant would loop forever against a persistently conflicting
  remote · severity: low · → mitigation: inline post-phase push_grant_termination_test

### Planned mitigations
- timing: pre-phase | name: baseline_sync_automerge_before_extraction | type: test | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: code-health — the extraction rewrites ait sync's only conflict-resolution path, and the task_git → _ait_data_git seam change | desc: record test_sync.sh and test_sync_branch_mode_automerge.sh PASS/FAIL summaries and observed tokens on the untouched tree, before any edit, as the diff baseline
- timing: pre-phase | name: sentinel_single_constant | type: refactor | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: goal-achievement — a drifted sentinel leaves TASK_*_AUTOMERGED unset while the merge worked | desc: declare the auto-merge sentinel once in task_utils.sh and have the emitter and both matchers reference that constant
- timing: pre-phase | name: bound_automerge_loop_iterations | type: enhancement | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: code-health — a looping resolver holding the pull mutex blocks every session's pull; the lengthened mutex window | desc: hard-cap ait_automerge_rebase_loop at 50 rounds, returning stuck-with-remaining on exhaustion so the caller aborts normally
- timing: post-phase | name: push_grant_termination_test | type: test | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: goal-achievement — the push progress grant adds a second termination condition to a retry loop | desc: fixture with a persistently re-conflicting remote asserting task_push stops at 5 push attempts and reports failed, counting attempts through an argv-keyed git shim

---

## Implementation notes (as landed)

All plan steps completed. Deviations and discoveries, in order:

**Pre-phase 1 — baseline (`baseline_sync_automerge_before_extraction`).** Measured
on the untouched tree before any edit: `tests/test_sync.sh` **42 passed / 0
failed**, `tests/test_sync_branch_mode_automerge.sh` **43 / 0**,
`tests/test_task_push.sh` **257 / 0**. No pre-existing failures, so every later
red would have been extraction damage. Post-extraction the first two read
**42 / 0** and **43 / 0** — identical — confirming the sync side is
behaviour-preserving. `shellcheck` was also baselined via
`git show HEAD:<file>`: the `CONTRIBUTE_*` SC2034 warnings in `task_utils.sh`
(17 of them) are pre-existing, and the change adds none.

**Progress channel — one deviation from the plan.** The plan said `iinfo_err`
"becomes plain stderr writes". That would have made the per-file
`Auto-merged: <f>` lines print on every pick, where the workflow pull must not
narrate. The library instead routes non-failure progress through an overridable
`AIT_AUTOMERGE_PROGRESS_FN`, defaulting to a no-op; `aitask_sync.sh` points it
at `iinfo_err`, so interactive `ait sync` keeps its per-file lines and `--batch`
stays silent exactly as before. Real failures were never on that channel — they
go through `warn()` and remain unsuppressible.

**A gap the plan missed: the notices were being swallowed.** The plan's stderr
sentinel works for *setting* `TASK_SYNC_AUTOMERGED`, but both callers capture
`_task_pull_rebase 2>&1` into a variable for `_task_push_classify`, so the
notice never reached a human — success was completely silent, and a fired round
cap was indistinguishable from an ordinary unmergeable conflict. Fixed by adding
`_task_pull_report_automerge`, which re-emits the two sentinel lines on the
*caller's* stderr (`task_sync` on both its success and failure paths, `task_push`
after each retry pull). Caught by tests 48/54/55/57, which failed against the
first implementation.

**Second sentinel constant.** The round cap needed the same
emitter/matcher-drift protection as the auto-merge line, so
`AIT_AUTOMERGE_GAVE_UP_SENTINEL` joins `AIT_PULL_AUTOMERGED_SENTINEL` in
`task_utils.sh`. Both live there rather than in the library because the matchers
run whether or not the library was ever loaded, and a matcher against an unset
variable matches every string.

**Scaffold rule: nothing owed.** `aitask_sync.sh` sources the new library at
startup, but no test scaffolds that script through
`setup_fake_aitask_repo` — every test that runs it copies the whole
`.aitask-scripts` tree. `task_utils.sh` loads the library lazily, so the
standalone fixtures are unaffected (pinned by test 51, which first asserts the
fixture really lacks the library so the check cannot be vacuous).

**Tests added.** `tests/test_task_push.sh` 48–58 (257 → **324** assertions) and
`tests/test_sync_branch_mode_automerge.sh` Test 9 (43 → **48**). Test 54's
discriminator reads `(2 file(s))` in the sentinel — a count of 1 would mean the
fixture degenerated into a single round.

**Docs.** `website/content/docs/commands/sync.md` only: a cross-reference in
"Auto-Merge Conflict Resolution" and a paragraph under "Task-data pull before
task selection". The batch-protocol table is untouched, and
`aitask_pick_own.sh --sync` still prints bare `SYNCED` as planned.
`check_links.py --build`: 29074 resolved, **0 broken**.

## Final Implementation Notes

- **Actual work done:** Extracted `ait sync`'s conflict resolver into
  `.aitask-scripts/lib/task_automerge.sh` (281 lines) and wired both `pull
  --rebase` paths to it. `aitask_sync.sh` lost `try_auto_merge`,
  `_rebase_advance`, `_resolve_conflict_path` and its hand-rolled advance loop
  (−172 lines) with every `--batch` token unchanged. `lib/task_utils.sh` gained
  the two sentinel constants, the `ait_rebase_is_ours` ownership-proof split, the
  lazy library loader, resolve-then-abort in `_task_pull_rebase_cleanup`,
  `TASK_SYNC_AUTOMERGED` / `TASK_PUSH_AUTOMERGED`, and the bounded push progress
  grant. All four planned inline risk mitigations landed. Tests: 257 → 324 in
  `test_task_push.sh`, 43 → 48 in `test_sync_branch_mode_automerge.sh`.

- **Deviations from plan:**
  - *Progress channel.* The plan turned `iinfo_err` into plain stderr writes;
    that would have made per-file `Auto-merged: <f>` lines print on every pick.
    Replaced with an overridable `AIT_AUTOMERGE_PROGRESS_FN` (no-op by default,
    `iinfo_err` in `aitask_sync.sh`), preserving both surfaces exactly.
  - *Second sentinel.* The round cap needed the same emitter/matcher-drift
    protection as the auto-merge line, so `AIT_AUTOMERGE_GAVE_UP_SENTINEL` was
    added next to `AIT_PULL_AUTOMERGED_SENTINEL`. Both live in `task_utils.sh`,
    not the library: the matchers run whether or not the library was loaded, and
    a matcher against an unset variable matches every string.
  - *Test 54's assertion string.* Written for a phrasing the emitter does not
    use; the assertion was corrected to the real text, which still carries the
    `(2 file(s))` discriminator. The behaviour was right, the assertion was not.

- **Issues encountered:** The plan's stderr sentinel set `TASK_*_AUTOMERGED`
  correctly but never reached a human — both callers capture `_task_pull_rebase
  2>&1` into a variable for `_task_push_classify`, so a successful auto-merge was
  entirely silent and a fired round cap was indistinguishable from an ordinary
  unmergeable conflict. Fixed with `_task_pull_report_automerge`, which re-emits
  the two sentinel lines on the *caller's* stderr (`task_sync` on both its
  success and failure paths, `task_push` after each retry pull). Tests 48, 54, 55
  and 57 failed against the first implementation and pass against the fix.

- **Key decisions:**
  - The library runs git through `_ait_data_git`, not `task_git` +
    `AIT_GIT_SKIP_STATE_CHECK=1`. Same worktree, same argv; it retires a
    documented guard-bypass rather than carrying it into a second caller.
    `test_sync_branch_mode_automerge.sh` Tests 2/3/7 still cover the
    staging-failure route because their shim keys on argv.
  - The auto-merge sits *behind* the same five-signal ownership gate as the
    abort. Auto-merging a rebase this call did not start is as dangerous as
    aborting one, so `ait_rebase_is_ours` was split out and is shared rather
    than duplicated.
  - `aitask_pick_own.sh --sync` still prints bare `SYNCED`; no
    `SYNCED:automerged`. The token is matched exactly by the pick skill and three
    existing assertions, the detail is actionable to none of them, and the human
    gets the stderr notice instead. The `ait sync --batch` protocol table is
    therefore unchanged.
  - `aitask_sync.sh` sources the library at startup while `task_utils.sh` loads
    it lazily. No `setup_fake_aitask_repo` entry is owed: no test scaffolds
    `aitask_sync.sh` itemized (they all copy the whole tree), and the lazy load
    is exactly what lets the standalone `task_utils.sh` fixtures degrade to "no
    auto-merge" instead of breaking.

- **Upstream defects identified:** None

## Post-Archival Corrections

Two defects found in review after t1727 archived, both confirmed and fixed in a
follow-up commit tagged `(t1727)`.

### 1. A recovered conflict poisoned the push failure classification (code defect)

`task_push` appended **every** `_task_pull_rebase` capture to `rebase_err`,
including git's own `CONFLICT (content)` text from a pull that then auto-merged
**successfully** — `_task_pull_rebase` forwards that text regardless of the
eventual outcome. `_task_push_classify` checks its `rebase_conflict` arm *ahead*
of the remote/diverged arms, so a later push failing on an unreachable remote
was reported as `rebase_conflict`, with the hint "rebase hit conflicts and was
aborted … local and remote diverge — reconcile with 'ait syncer'". Both halves
were false: the rebase had succeeded, and the real blocker was the network.

This was **introduced by t1727**. Before it, a conflicted pull never
auto-recovered, so `CONFLICT` in `rebase_err` always meant a genuinely
unresolved conflict.

Fixed by splitting the accumulator in two: `rebase_err` still collects
everything and feeds the user-facing `unknown` detail line, while a new
`rebase_block` — fed **only** by pulls that returned non-zero — is the sole
input to `_task_push_classify`. The rule is keyed on the pull's exit status
("a pull that succeeded describes no blocker"), not on the auto-merge sentinel,
because that is the general statement and is behaviour-preserving for every
pre-t1727 case, where rc 0 already implied git printed no conflict text.

### 2. Test 58 never reached the progress grant (vacuous test)

The original fixture rejected every push but created **no** remote conflict, so
`_task_pull_rebase` succeeded cleanly, emitted no sentinel, and the grant branch
was never entered. Its `1..5` range assertion also accepted the pre-grant
three-attempt loop, so it could not have detected the grant being absent.

Rebuilt: the push shim now advances the remote with a fresh conflicting
`boardcol` edit on every rejection, so each retry pull finds a real conflict and
auto-merges it. The assertion is now the **exact** count `5`
(`max_attempts` 3 + `_AIT_PUSH_PROGRESS_GRANTS` 2), plus
`TASK_PUSH_AUTOMERGED=1` as the precondition that the grant was actually
reached.

### Mutation-verified

Neither test is a tautology; each was run against a mutant of the half it covers:

| mutant | expected | observed |
|---|---|---|
| classify against `$rebase_err` again | Test 59 fails | `expected 'remote_unreachable', got 'rebase_conflict'` + the wrong hint (2 assertions) |
| `_AIT_PUSH_PROGRESS_GRANTS=0` | Test 58 fails | `expected '5', got '3'` — confirming the old `1..5` range accepted the pre-grant loop |

### Also added

- **Test 60** — the other direction of Test 59: an *unrecovered* body conflict
  must still classify as `rebase_conflict`. Narrowing the classifier's input
  must not make it blind to a conflict that genuinely did not resolve.
- **`advance_remote_task` now verifies it advanced the remote.** Its clone and
  push swallowed errors with `2>/dev/null`; when either silently failed, the
  remote was never ahead and the test failed on its *behaviour* assertions
  instead of naming the broken fixture. This was observed once as a transient
  2-failure run. A precondition that can fail silently is not a precondition.

`tests/test_task_push.sh`: 324 → **346** assertions, stable across three
consecutive runs. `test_sync.sh` 42/0, `test_sync_branch_mode_automerge.sh`
48/0, `test_task_git.sh` 105/0, `test_sync_deferral_and_quarantine.sh` 52/0,
`test_task_commit_scoped.sh` 63/0. No new shellcheck warnings.
