---
Task: t1265_ait_git_push_silently_reports_success_when_it_pushed_nothing.md
Base branch: main
Output branch: main
plan_verified: []
---

# t1265 — `ait git push` silently reports success when it pushed nothing

## Context

`task_push()` (`.aitask-scripts/lib/task_utils.sh:192-207`) is a best-effort
push: try push → `pull --rebase` → retry, 3 times, then `return 0` no matter
what. Both internal helpers discard stderr (`2>/dev/null`), so a *completely
failed* push is byte-for-byte indistinguishable from a successful one — no
output, exit 0.

Observed live at the end of the t635_27 verification run: `./ait git push`
printed nothing, exited 0, and pushed nothing. `git push` was rejected
(non-fast-forward: `origin/aitask-data` had advanced from a concurrent session)
and `git pull --rebase` refused (`cannot pull with rebase: You have unstaged
changes` — another session's uncommitted edits in the data worktree). Three
commits (verification state, plan, archival) were stranded with zero signal.

On a shared checkout this is a steady state, not an edge case: a dirty data
worktree permanently blocks the rebase fallback, so archival and gate-ledger
commits can silently fail to reach the remote exactly when concurrency makes it
most likely. Another PC then picks a task that is already done.

**Goal:** keep the non-fatal contract (never abort the workflow, exit 0 for every
push outcome), but stop being silent — report *what* is stranded and *why*, with
an actionable recovery hint, and expose a machine-readable outcome to **both**
in-process and cross-process callers.

## The outcome contract (explicit, and the thing the tests pin)

`task_push` has two distinct audiences, and in-process globals only serve one of
them (`./ait git push` is a separate process — a subprocess caller such as
`chatlink/task_create.py:119-128` can never read them). Both tiers are therefore
part of the contract:

| Tier | Consumer | Interface |
|---|---|---|
| **In-process** | scripts that `source task_utils.sh` (`aitask_pick_own.sh`, `aitask_gate_record.sh`) | globals `TASK_PUSH_STATUS` / `TASK_PUSH_REASON` / `TASK_PUSH_UNPUSHED` |
| **Cross-process, human** | `./ait git push` in a terminal or captured in a log | a `warn` line on **stderr**; silent on success |
| **Cross-process, machine** | `./ait git push --batch` from another program | **one structured line on stdout** |

`--batch` output tokens, deliberately reusing the vocabulary the framework
already documents for `ait sync --batch`
(`website/content/docs/commands/sync.md:36-48`):

| Line | Meaning |
|---|---|
| `PUSHED` | local commits reached the remote |
| `NOTHING` | already up to date, nothing to push |
| `NO_REMOTE` | no git remote configured |
| `FAILED:<reason>:<count>` | push failed; `<reason>` is a classifier code, `<count>` the unpushed count (`unknown` when undeterminable) |

**Exit status is 0 for every push outcome, including `FAILED:` — one exception,
by design:** the pre-flight `assert_data_worktree_clean push`
(`task_utils.sh:95-123`) still `die`s (exit 1) when the data worktree is wedged
mid-rebase/merge/cherry-pick. That is not a push outcome — it is a "your data
worktree is broken, here is how to recover" guard that predates this task, it is
loud rather than silent (so it does not regress the bug being fixed), and it is
bypassable with `AIT_GIT_SKIP_STATE_CHECK=1`. It is documented as the exception
and pinned by a regression test rather than left as an accident of ordering.

**`TASK_PUSH_UNPUSHED` is a current reading, not an atomic snapshot.** It is
sampled with `rev-list --count @{upstream}..HEAD` *after* the push cycle
finishes; on a shared checkout another session can move refs between the failure
and the sample, so the count is "how many commits are unpushed now", not "how
many the failed push would have carried". This is stated in the code comment, in
the globals' doc block, and in the user docs; nothing in the message or the
`--batch` line implies the count and the reason were captured atomically.

## Design

### 1. Shared data-worktree git seam

The `if [[ "$_AIT_DATA_WORKTREE" != "." ]]; then git -C … else git … fi` shape is
already duplicated in `_task_push_once` and `_task_pull_rebase`, and the new
probes need it three more times. Introduce one internal seam and route all of
them through it:

```bash
# Internal: run git against the task-data worktree (branch mode) or the current
# repo (legacy mode). LC_ALL=C keeps git's messages parseable by the failure
# classifier below.
_ait_data_git() {
    _ait_detect_data_worktree
    if [[ "$_AIT_DATA_WORKTREE" != "." ]]; then
        LC_ALL=C git -C "$_AIT_DATA_WORKTREE" "$@"
    else
        LC_ALL=C git "$@"
    fi
}
```

`_task_push_once` becomes `_ait_data_git push --quiet`; `_task_pull_rebase`
becomes `_ait_data_git pull --rebase --quiet`. Behaviour is unchanged (existing
Tests 1–8 cover both modes); `LC_ALL=C` makes classification locale-independent.

This seam is deliberately *not* `task_git()` — `task_git` runs
`assert_data_worktree_clean`, which `task_push` already calls once up front.

### 2. Outcome globals

```bash
# Outcome of the most recent task_push call. task_push always returns 0 for a
# push outcome (best-effort contract) — read these when the outcome matters.
# TASK_PUSH_UNPUSHED is sampled after the push cycle: a current count, not an
# atomic snapshot of the failure (concurrent sessions can move refs meanwhile).
TASK_PUSH_STATUS=""     # pushed | up-to-date | no-remote | failed
TASK_PUSH_REASON=""     # reason code when failed (see _task_push_classify)
TASK_PUSH_UNPUSHED=""   # unpushed commit count; "" when undeterminable
```

Reset at the very top of `task_push`, before the pre-flight guard, so a `die` can
never leave a previous call's values readable as if they described this one.

### 3. Read-only probes (each returns 0 — `set -e` safety)

Every one is consumed via `x="$(helper)"`, which under `set -euo pipefail` in a
sourced script would abort the *caller* if the helper exited non-zero. They
therefore swallow their own failure and print nothing:

```bash
_task_push_unpushed_count() { _ait_data_git rev-list --count '@{upstream}..HEAD' 2>/dev/null || true; }
_task_push_upstream()       { _ait_data_git rev-parse --abbrev-ref --symbolic-full-name '@{upstream}' 2>/dev/null || true; }
_task_push_has_remote()     { [[ -n "$(_ait_data_git remote 2>/dev/null || true)" ]]; }
```

### 4. Pure failure classifier + hint table

Pure string→code function (no git calls, no I/O) so every reason is unit-testable
from fixtures instead of five elaborate git setups:

```bash
# Internal: classify a failed push cycle from captured git output.
# $1 = push stderr, $2 = accumulated pull --rebase stderr.
# Prints: dirty_worktree | rebase_conflict | remote_unreachable | diverged | unknown
_task_push_classify() { … }
```

Match order (first hit wins) — the rebase blocker is checked before the push
rejection because the rejection is only the *symptom*:

| Order | Code | Matched in | Substrings |
|---|---|---|---|
| 1 | `dirty_worktree` | rebase err | `cannot pull with rebase`, `unstaged changes`, `uncommitted changes`, `local changes` + `would be overwritten` |
| 2 | `rebase_conflict` | rebase err | `CONFLICT`, `could not apply`, `Resolve all conflicts`, `rebase-merge directory`, `rebase-apply` |
| 3 | `remote_unreachable` | either | `Could not read from remote repository`, `does not appear to be a git repository`, `Could not resolve host`, `Connection refused`, `Authentication failed`, `Permission denied`, `unable to access`, `No configured push destination`, `timed out` |
| 4 | `diverged` | push err | `non-fast-forward`, `fetch first`, `rejected`, `behind its remote` |
| 5 | `unknown` | — | fallback |

`_task_push_reason_hint <code>` maps each code to an actionable sentence:

- `dirty_worktree` → `data worktree has unstaged changes blocking rebase; reconcile with 'ait syncer'`
- `rebase_conflict` → `rebase stopped on conflicts; recover with './ait git rebase --abort' (or resolve and './ait git rebase --continue')`
- `remote_unreachable` → `remote unreachable (network, auth, or no push destination); retry './ait git push' once connectivity is restored`
- `diverged` → `remote has diverged (non-fast-forward) and the rebase retries did not resolve it; reconcile with 'ait syncer'`
- `unknown` → `reason unknown; run './ait git-health' and inspect the data worktree manually` — plus ` (git: <first non-empty output line>)` appended by the caller, so an unclassified failure still carries git's own words.

### 5. `task_push` rewrite

```bash
task_push() {
    TASK_PUSH_STATUS=""; TASK_PUSH_REASON=""; TASK_PUSH_UNPUSHED=""
    assert_data_worktree_clean push        # documented exception: dies if wedged

    # No remote at all (solo / offline-only repo): nothing to push to, and
    # nothing is at risk — stay silent, as before.
    if ! _task_push_has_remote; then
        TASK_PUSH_STATUS="no-remote"
        return 0
    fi

    local before_count push_err="" rebase_err="" out="" detail=""
    before_count="$(_task_push_unpushed_count)"

    local max_attempts=3 attempt
    for (( attempt=1; attempt<=max_attempts; attempt++ )); do
        if push_err="$(_task_push_once 2>&1)"; then
            [[ "$before_count" == "0" ]] && TASK_PUSH_STATUS="up-to-date" \
                                         || TASK_PUSH_STATUS="pushed"
            TASK_PUSH_UNPUSHED="$(_task_push_unpushed_count)"
            return 0
        fi
        if (( attempt < max_attempts )); then
            out="$(_task_pull_rebase 2>&1)" || true
            rebase_err+="${out}"$'\n'      # accumulate: attempt 1's blocker is
        fi                                  # the real cause, attempt 2 only echoes it
    done

    TASK_PUSH_STATUS="failed"
    TASK_PUSH_REASON="$(_task_push_classify "$push_err" "$rebase_err")"
    TASK_PUSH_UNPUSHED="$(_task_push_unpushed_count)"   # current count (see contract)
    … compose "$detail" for the unknown case …
    _task_push_warn "$detail"
    return 0                                # best-effort contract preserved
}
```

`_task_push_warn` decides whether the failure is worth a user-facing warning —
**warn only when commits are actually stranded**:

| `TASK_PUSH_UNPUSHED` | Message |
|---|---|
| `>0` | `Warning: 3 commit(s) not pushed to origin/aitask-data — data worktree has unstaged changes blocking rebase; reconcile with 'ait syncer'` |
| `""` (no upstream) | `Warning: task data push failed (unpushed commit count unavailable) — <hint>` |
| `0` | *silent* — the push failed (e.g. offline) but nothing local is at risk |

The `0` and `no-remote` silent paths are what keep this from becoming per-command
noise for offline and single-machine users, whose pushes fail routinely today
with nothing pending. `warn()` writes to stderr (`terminal_compat.sh:21`), per
the shell-conventions rule that diagnostics must survive `$(...)` capture.

### 6. `task_push_report` — the cross-process machine surface

```bash
# Print the one-line structured outcome of the last task_push (--batch surface).
task_push_report() {
    case "$TASK_PUSH_STATUS" in
        pushed)     echo "PUSHED" ;;
        up-to-date) echo "NOTHING" ;;
        no-remote)  echo "NO_REMOTE" ;;
        failed)     echo "FAILED:${TASK_PUSH_REASON}:${TASK_PUSH_UNPUSHED:-unknown}" ;;
        *)          echo "ERROR:no-push-run" ;;
    esac
}
```

### 7. `./ait git push [--batch]`

`ait:326-332` currently ignores every argument after `push`. Keep that (any
unrecognised arg still runs a plain best-effort push, unchanged) and add only the
`--batch` opt-in. `ait` runs `set -euo pipefail`, so the flag scan must not end on
a false test:

```bash
git)  shift; source "$SCRIPTS_DIR/lib/task_utils.sh"
      if [[ "${1:-}" == "push" ]]; then
          shift
          push_batch=0
          for arg in "$@"; do
              if [[ "$arg" == "--batch" ]]; then push_batch=1; fi
          done
          task_push
          if [[ "$push_batch" == "1" ]]; then task_push_report; fi
      else
          task_git "$@"
      fi
      ;;
```

### 8. One call site un-muted

`.aitask-scripts/aitask_gate_record.sh:83` calls `task_push 2>/dev/null || true`.
That `2>/dev/null` was there to swallow git's noise — which `task_push` now
captures internally — and it would swallow the new warning too. Change to
`task_push || true`. The other two call sites (`ait:329`,
`aitask_pick_own.sh:256`) already let stderr through.

## Files to modify

| File | Change |
|---|---|
| `.aitask-scripts/lib/task_utils.sh` | `_ait_data_git` seam; outcome globals; `_task_push_unpushed_count` / `_task_push_upstream` / `_task_push_has_remote` / `_task_push_classify` / `_task_push_reason_hint` / `_task_push_warn`; `task_push` rewrite; `task_push_report`; `_task_push_once` / `_task_pull_rebase` routed through the seam |
| `ait` | `git push` accepts `--batch` → emit `task_push_report` line |
| `.aitask-scripts/aitask_gate_record.sh` | drop `2>/dev/null` from the `task_push` call (line 83) |
| `tests/test_task_push.sh` | new tests + status assertions on existing tests 1/3/5 |
| `tests/test_gate_record.sh` | new remote-backed scenario proving the un-muted warning reaches stderr |
| `website/content/docs/commands/sync.md` | new `## ait git push` section: best-effort semantics, the warning, the `--batch` protocol table, the pre-flight exception, the count-sampling caveat |
| `website/content/docs/commands/_index.md` | one quick-reference line for `ait git push --batch` |

## Tests

### `tests/test_task_push.sh`

Existing tests 1–9 must keep passing unchanged (they pin the success/rebase/exit-0
contract in both legacy and branch mode). Added:

- **Extend Tests 1/3** — assert `TASK_PUSH_STATUS=pushed` on the clean push and on
  the push-after-rebase path.
- **Extend Test 5** (unreachable remote, 1 pending commit) — assert exit 0 *and*
  `TASK_PUSH_STATUS=failed`, `TASK_PUSH_REASON=remote_unreachable`, and that
  stderr contains `1 commit(s) not pushed`.
- **Classifier table (pure unit).** One fixture per reason code fed straight to
  `_task_push_classify`, asserting each distinct code — including the
  discriminating case where the push says `non-fast-forward` **and** the rebase
  says `unstaged changes` → must classify `dirty_worktree`, not `diverged`.
- **Flagship live scenario (branch mode).** Local commit + `advance_remote` + an
  *unstaged edit to a tracked file* in `.aitask-data` (with `git config
  rebase.autoStash false` so the outcome is deterministic regardless of the
  developer's global config). Assert: exit 0, remote unchanged (still 2 commits —
  nothing was pushed), `TASK_PUSH_STATUS=failed`,
  `TASK_PUSH_REASON=dirty_worktree`, `TASK_PUSH_UNPUSHED=1`, and stderr contains
  both `1 commit(s) not pushed` and `ait syncer`. This is the exact live failure
  from the task description.
- **Nothing to push** → `TASK_PUSH_STATUS=up-to-date`, exit 0, **no** stderr
  (negative control against warning noise).
- **No remote configured** → `TASK_PUSH_STATUS=no-remote`, exit 0, no stderr
  (negative control: the silent path solo users depend on).
- **Pre-flight exception (documented `die`).** Branch-mode fixture with
  `mkdir -p .git/worktrees/-aitask-data/rebase-merge` so `_ait_data_gitdir`
  resolves and the guard fires. Run in a subshell — `( task_push )` — and assert
  exit **1** plus a stderr message naming `rebase` and `--abort`; then assert
  `AIT_GIT_SKIP_STATE_CHECK=1 ( task_push )` exits 0. This pins the one exception
  to the exit-0 contract instead of leaving it implicit.
- **`--batch` cross-process contract — all four tokens** (fake-repo scaffold, as
  Test 8 does). `--batch` is now a public machine interface, so every documented
  token is asserted through the real `./ait git push --batch` entry point, not
  just through the in-process globals — a future `case`-label typo or
  status→token mapping regression must fail the suite:

  | Fixture state | Expected stdout | Also asserted |
  |---|---|---|
  | one local commit, reachable remote | `PUSHED` | exit 0; remote advanced |
  | nothing to push (already in sync) | `NOTHING` | exit 0; **empty stderr** |
  | `git remote remove origin` | `NO_REMOTE` | exit 0; **empty stderr** |
  | one pending commit, remote URL broken | `FAILED:remote_unreachable:1` | exit 0; warning on stderr |

  Plus a negative control: plain `./ait git push` (no `--batch`) prints
  **nothing on stdout** in every one of those states, so the human surface stays
  clean and the token line is strictly opt-in.

  Fixtures are built with `git init` / `git clone` and `mkdir`, never `cp -a` of
  a repo that has worktrees (absolute `.git/worktrees` gitdir pointers make a
  copied repo commit back into the original).

### `tests/test_gate_record.sh`

The existing fixture has no remote, so the warning is silent there and would not
notice a re-muted call site. Add a second fixture that actually exercises it:
clone a bare remote, seed the task file, commit and push (so an upstream exists),
then `git remote set-url origin /nonexistent/repo.git`. Run the wrapper:

```bash
out="$( cd "$TMP2" && TASK_DIR=aitasks "$RECORD" 77 plan_approved pass type=human 2>&1 >/dev/null )"; rc=$?
```

Assert `rc == 0`, that the gate block was still committed locally (the wrapper's
durability promise), and that `out` contains `commit(s) not pushed` — i.e. the
warning survives the call site's redirections. This is the regression test that
fails if the `2>/dev/null` ever comes back.

## Verification

```bash
bash tests/test_task_push.sh          # must print "N passed, 0 failed" and exit 0
bash tests/test_gate_record.sh        # incl. the new un-muted-warning scenario
bash tests/test_task_git.sh           # task_push / ait git push integration
shellcheck .aitask-scripts/lib/task_utils.sh .aitask-scripts/aitask_gate_record.sh
```

Harness-failure proof (per the "prove the test harness can fail" rule): after the
suites are green, temporarily flip one new assertion in each touched suite to a
wrong expected value and confirm the suite exits **1** and names the failure, then
restore it.

`tests/test_task_push.sh` must, among the rest, exercise **all four** documented
`--batch` tokens end-to-end — `PUSHED`, `NOTHING`, `NO_REMOTE`, and
`FAILED:<reason>:<count>` — one fixture each (see the `--batch` cross-process
table above). Treat a missing token as an incomplete implementation: this is a
public machine interface, so a `case`-label typo in `task_push_report` must fail
the suite rather than silently break a consumer.

Live check on this repo (branch mode, real remote): `./ait git push` on a clean
tree stays silent and exits 0; `./ait git push --batch` prints one of
`PUSHED` / `NOTHING`.

## Risk

### Code-health risk: medium

- `task_push` is on the hot path of every workflow (`ait git push`,
  `aitask_pick_own.sh`, `aitask_gate_record.sh`); the new helpers are consumed via
  `x="$(helper)"` inside scripts running `set -euo pipefail`, so a helper that
  leaks a non-zero status would abort the caller with no visible error — the exact
  footgun `aidocs/framework/shell_conventions.md` documents · severity: medium ·
  → mitigation: every probe ends in `|| true`, the `ait` flag scan avoids a
  trailing false test; pinned by the up-to-date / no-remote tests, which run
  `task_push` on paths where `rev-list` / `remote` return non-zero.
- Turning a previously silent failure into a warning risks per-command noise for
  offline / single-machine users · severity: medium · → mitigation: the
  `no-remote` and `unpushed == 0` silent paths, each pinned by a no-stderr
  negative control.
- Adding a `--batch` surface to `ait git push` widens the CLI's public contract ·
  severity: low · → mitigation: opt-in flag only, default output byte-identical
  to today (asserted), and the token vocabulary is reused from the already
  documented `ait sync --batch` protocol rather than invented.
- Classification is substring matching on git's human-readable output, which can
  drift across git versions or locales · severity: low · → mitigation: `LC_ALL=C`
  in the shared seam, multiple alternative substrings per code, and an `unknown`
  fallback that still warns and quotes git's own first line — no failure mode is
  silent even when classification misses.

### Goal-achievement risk: low

- The acceptance criterion is precise and directly reproducible (the flagship test
  stages the exact live failure), so "delivered but wrong" is unlikely · severity:
  low · → mitigation: none needed.
- `task_sync()` (`task_utils.sh:181`) has the same swallow-everything shape and is
  *not* covered here · severity: low · → mitigation: out of scope by the task's
  own wording ("Return a distinct status from `task_push`"); disposition:
  **documented-only**, noted here rather than silently widened.
- `chatlink/task_create.py:119-128` runs `ait git push` in a subprocess and only
  inspects the return code, so it will still log "push failed" as a no-op even
  though the `--batch` line is now available to it · severity: low · →
  mitigation: disposition **documented-only** — this task ships the contract the
  caller needs; wiring chatlink to `--batch` is a separate, independently
  testable change and is not required by t1265's acceptance criterion.

No mitigation tasks were confirmed: each identified risk is covered by a test in
this task (the `set -e` probe safety and the noise regression by the negative
controls, the CLI-widening by the default-output assertion, and classification
drift by the `unknown`-still-warns fallback).

## Post-implementation

Per **Step 9**: merge target `main` (current-branch profile — no worktree to
clean up), then archive t1265 via `./.aitask-scripts/aitask_archive.sh 1265`.
The `risk_evaluated` gate is the only active gate for this task.

Follow-up housekeeping: the memory note
`project_ait_git_push_silent_noop_on_divergence` states that `ait git push` can
exit 0 having pushed nothing *with no signal* — once this lands, that note must be
updated to say the failure is now reported (the merge-base verification advice
stays valid).

## Final Implementation Notes

- **Actual work done:** Implemented exactly as planned. `task_utils.sh` gained
  the `_ait_data_git` seam (LC_ALL=C, used by both push helpers and the three
  probes), the `TASK_PUSH_STATUS` / `TASK_PUSH_REASON` / `TASK_PUSH_UNPUSHED`
  globals, a rewritten `task_push`, `task_push_report`, and the
  `_task_push_classify` / `_task_push_reason_hint` / `_task_push_warn` /
  `_task_push_first_line` helpers. `ait` learned `git push --batch`;
  `aitask_gate_record.sh` lost its `2>/dev/null`. Tests: 6 new blocks in
  `test_task_push.sh` (18 → 63 assertions) and a remote-backed scenario in
  `test_gate_record.sh` (13 → 16). Docs: a full `## ait git push` section in
  `commands/sync.md` plus two `commands/_index.md` lines.
- **Deviations from plan:** None functional. Two spots were written as explicit
  `if` blocks instead of the plan's `[[ … ]] && x=…` shorthand (`task_push`'s
  up-to-date branch and `_task_push_warn`'s upstream prefix) to remove any doubt
  about `set -e` behaviour on a false test.
- **Issues encountered:** None blocking. The only judgement call was where to
  keep silence: a failed push with 0 unpushed commits, and a repo with no remote
  at all, stay quiet — otherwise every offline/solo `ait git push` would warn.
  Both are pinned by no-stderr negative controls so the silence is intentional
  rather than incidental.
- **Key decisions:**
  - Exit status stays 0 for every push outcome; the machine-readable outcome is
    carried by globals in-process and by the opt-in `--batch` line
    cross-process. In-process globals alone would have been invisible to
    `./ait git push` callers (a separate process).
  - The rebase blocker is classified *before* the push rejection: the rejection
    is only the symptom, and hinting at the wrong recovery is worse than not
    hinting at all.
  - `TASK_PUSH_UNPUSHED` is documented as a current reading, not an atomic
    snapshot — under concurrency refs can move between the failure and the
    sample.
  - The pre-flight `assert_data_worktree_clean` die is documented as the one
    exception to exit-0 and pinned by a regression test (plus its
    `AIT_GIT_SKIP_STATE_CHECK=1` bypass) rather than left implicit.
- **Verification performed:** `test_task_push.sh` 63/63, `test_gate_record.sh`
  16/16, `test_task_git.sh` 17/17, plus `test_archive_folded.sh`,
  `test_crash_recovery_pid_anchor.sh`, `test_claim_id.sh`,
  `test_archive_verification_gate.sh` — all pass. `shellcheck` on the three
  touched shell files reports no new findings (only pre-existing SC1091/SC2001/
  SC2086/SC2034). Two negative controls were run and reverted: stubbing
  `_task_push_warn` to a no-op fails 5 assertions across Tests 5/11/15 (exit 1),
  and restoring `2>/dev/null` at the gate-record call site fails its new
  assertion (exit 1). Live end-to-end on this repo: `./ait git push --batch`
  printed `FAILED:dirty_worktree:16` with the warning, in the very situation
  that previously printed nothing and exited 0.
- **Upstream defects identified:** None.
