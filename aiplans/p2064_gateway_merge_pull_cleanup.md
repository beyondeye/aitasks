---
Task: t2064_gateway_merge_pull_cleanup.md
Base branch: main
Output branch: main
---

# t2064 — `./ait git pull`: abort a merge-mode pull's own stopped merge

## Context

t1739 routed `./ait git pull` through `_ait_owned_pull`
(`.aitask-scripts/lib/task_utils.sh`), which auto-merges or aborts a conflicted
**rebase** it can prove it started (`ait_rebase_is_ours`: the rebase's
`orig-head` == the HEAD read just before the pull, under the pull mutex). A
**merge-mode** pull (`-c pull.rebase=false`, `--no-rebase`) that stops leaves
`MERGE_HEAD`. That happens on a conflict, or when a hook refuses the merge
commit. The pull reports it as `data_midop` and never cleans it up, so every
later `./ait git` write is refused until the user runs
`./ait git merge --abort`. This task adds ownership evidence for a merge this
pull started, so the gateway can abort its own stopped merge. A merge started
elsewhere, or one the user paused deliberately, is never touched.

**Decided scope (user, review round 2):** recognition of a stopped merge stays
a **list of git message families**. It is explicitly **not exhaustive**: a
stopped merge whose output matches no family is left untouched and needs manual
recovery. That limit is documented, and no doc claims cleanup always succeeds.
trace2-based detection is out of scope for this task.

### Verified facts (probed against git 2.56 in a linked-worktree scratch repo, `LC_ALL=C`)

- `MERGE_HEAD`, `ORIG_HEAD` **and `FETCH_HEAD`** all live in the
  **per-worktree** git-dir (`.git/worktrees/<wt>/`). That is the same `gitdir`
  `_ait_owned_pull` already reads.
- Every stop below leaves `MERGE_HEAD` with `ORIG_HEAD` == HEAD before the
  pull and `MERGE_HEAD` == the `FETCH_HEAD` for-merge SHA. The output each one
  prints, with `-q` noted where it differs:

  | stop | rc | output marker(s) |
  |---|---|---|
  | conflict | 1 | `CONFLICT (…)`, `Automatic merge failed` (also under `-q`) |
  | `pre-merge-commit` / `commit-msg` / `prepare-commit-msg` refusal, emptied message | 1 | `Not committing merge; use 'git commit' to complete the merge.` |
  | commit object not written (signing: `commit.gpgSign` + failing `gpg.program`) | 128 | `error: gpg failed to sign the data`, `fatal: failed to write commit object` |
  | commit written, branch update rejected (`reference-transaction` hook, `prepared` phase) | 128 | `Merge made by the 'ort' strategy.` (**absent under `-q`**) + `fatal: in 'prepared' phase, update aborted by the reference-transaction hook` |

- **The ref-transaction fatal is NOT merge evidence** (review round 3,
  reproduced). `git fetch` prints the identical line when its own transaction
  is rejected. A `prepared`-phase hook on `refs/remotes/origin/<branch>` can
  run a raw `git merge --no-ff --no-commit <fetched sha>` (hooks off, output
  discarded) and then reject the fetch. The pull exits 1 printing only that
  fatal. `ORIG_HEAD` == `head_before` and `MERGE_HEAD` == the `FETCH_HEAD`
  for-merge SHA, so every evidence gate passes for a merge the pull's merge
  step never started. Only `Merge made by` is printed by the pull's own merge
  step, so it alone marks this family. Under `-q` that line is absent: the
  branch-update stop then carries no merge-specific marker, and it is left in
  place for manual recovery (the accepted bound).

- `git merge --abort` restores HEAD in every case, including the
  post-commit ref-update one (verified). It also keeps an unrelated
  **unstaged** edit (verified). A **staged** unrelated change makes the merge
  refuse before it starts (no `MERGE_HEAD`), so the abort never meets another
  session's staged work.
- `pull --no-commit` with no conflict → rc 0 + `MERGE_HEAD` (the deliberate
  pause). rc 0 never reaches the cleanup; the existing completion postcondition
  reports it as unverified and leaves it alone. This does not change.
- `_ait_data_git` runs git under `LC_ALL=C`, so the markers are not localized.

## Design

The merge is treated as this pull's own only when **every one** of these holds.
Missing any one leaves it untouched:

0. the pull mutex is held (unchanged);
1. nothing was in progress before the pull (unchanged signal 1);
2. `MERGE_HEAD` is in progress after it (signal 2);
3. the pull's own output carries a **recognised, merge-specific stop
   marker**: a line only git's merge step prints, never a generic fatal that
   another step (fetch, a hook) can also print. This is signal 3, widened only
   for an owned merge through one named predicate, `_ait_merge_stop_shaped
   <out>`, with the four families in the table above, where the fourth is
   matched by `Merge made by` **only**. The other markers come only from
   git's merge or commit machinery (`CONFLICT` / `Automatic merge failed`
   from the merge strategy, `Not committing merge` from merge's
   `abort_commit`, `failed to write commit object` from commit creation),
   which fetch never runs. A hook that deliberately *prints* one of those
   lines forges evidence on purpose and is outside this rule's threat model,
   as it is for the rebase rule's conflict text.
   Output that matches no family fails closed: the merge is left in place and
   reported as `data_midop`, which is today's behaviour, and needs manual
   recovery. That output is also exactly what a pull that failed *before* its
   merge ran produces, for example on `index.lock` contention with a concurrent
   foreign merge;
4. **the pull was a merge-mode pull.** The gateway resolves the mode and passes
   `--own-merge` only in merge mode. The workflow pull (`_task_pull_rebase`,
   always `--rebase`) never passes it;
5. `ait_merge_is_ours`: `ORIG_HEAD` == `head_before`, **and** the `MERGE_HEAD`
   SHA list == the `FETCH_HEAD` for-merge SHA list (same order, non-empty).

On proof the merge is aborted and the abort is verified: the state must be
gone. **A merge-mode conflict is never auto-merged.** The auto-merge engine is
a rebase-replay loop, and the task allows abort-only.

### 1. `.aitask-scripts/lib/task_utils.sh`

**a. New sentinel constant**, next to `AIT_PULL_UNVERIFIED_SENTINEL`, following
the same one-spelling rule (emitter and classifier both read it):

```bash
# Emitted by _task_pull_rebase_cleanup when it aborted a merge-mode gateway pull's
# own stopped merge (t2064); matched by _task_push_classify -> merge_aborted.
# Free of "rebase", "CONFLICT" and "the data worktree is mid-" so it can only
# match its own arm.
AIT_PULL_MERGE_ABORTED_SENTINEL="merge aborted after it stopped"
```

**b. `ait_merge_is_ours <gitdir> <head_before> <state>`** and
**`ait_merge_abort_if_ours <runner> <gitdir> <head_before> <state>`**, placed
directly after the rebase pair. They are the single evidence rule for the merge
operation and mirror the rebase pair's shape and verdict tokens
(`aborted` / `abort_failed` / `not_ours`, always rc 0, runner never invoked on
`not_ours`):

```bash
ait_merge_is_ours() {
    local gitdir="$1" head_before="$2" state="$3" orig merge_heads fetch_heads="" line rest
    [[ "$state" == "MERGE_HEAD" && -n "$head_before" ]] || return 1
    # Read as files, like the rebase rule's orig-head: a ref backend that does
    # not keep ORIG_HEAD as a file (reftable) fails closed — merge left in place.
    orig="$(head -n1 "$gitdir/ORIG_HEAD" 2>/dev/null || true)"
    [[ -n "$orig" && "$orig" == "$head_before" ]] || return 1
    [[ -r "$gitdir/FETCH_HEAD" ]] || return 1
    merge_heads="$(cat "$gitdir/MERGE_HEAD" 2>/dev/null || true)"
    # FETCH_HEAD: "<sha>\t<''|not-for-merge>\t<desc>". Split by expansion, not
    # IFS=$'\t' read — tab is IFS whitespace, so consecutive tabs would collapse.
    while IFS= read -r line || [[ -n "$line" ]]; do
        rest="${line#*$'\t'}"
        [[ "${rest%%$'\t'*}" == "not-for-merge" ]] && continue
        fetch_heads+="${line%%$'\t'*}"$'\n'
    done < "$gitdir/FETCH_HEAD"
    fetch_heads="${fetch_heads%$'\n'}"
    [[ -n "$merge_heads" && "$merge_heads" == "$fetch_heads" ]]
}
```

`ait_merge_abort_if_ours` is `ait_rebase_abort_if_ours`, except that it gates
on `ait_merge_is_ours` and runs
`"$runner" "${AIT_RECONCILE_GIT_OPTS[@]}" merge --abort`. The rerere pin
matters here because `merge --abort` runs `rerere clear`. It then verifies
`_ait_inprogress_state_at "$gitdir"` is empty. Add its call site to the
`AIT_RECONCILE_GIT_OPTS` SCOPE comment.

**c. `_ait_merge_stop_shaped <out>`** (0/1 only), next to the cleanup. The
comment carries the probed table above and says plainly that the list is not
exhaustive and that unmatched output fails closed:

```bash
_ait_merge_stop_shaped() {
    case "$1" in
        *CONFLICT*|*"Automatic merge failed"*) return 0 ;;   # conflict
        *"Not committing merge"*) return 0 ;;               # commit refused: every hook refusal, empty message
        *"failed to write commit object"*) return 0 ;;      # commit not written: signing / object write
        *"Merge made by"*) return 0 ;;                      # commit written, then the branch update failed
        # NOT the ref-transaction fatal on its own: git fetch prints the identical
        # line, so it proves nothing about a merge (t2064 review). Under -q the
        # "Merge made by" line is suppressed, so that stop stays unrecognised.
    esac
    return 1
}
```

**d. `_ait_owned_pull [--own-merge] <git argv…>`.** If `$1` is `--own-merge`,
set `own_merge=1` and shift. This is unambiguous: every caller's argv starts
with `-c`. Pass it to `_task_pull_rebase_cleanup` as a 5th argument. Update the
docblock.

**e. `_task_pull_rebase_cleanup gitdir before head_before out [own_merge]`**
(default `0`):
- Signal 3: compute `stopped` from the existing conflict patterns. Also set it
  when `own_merge==1`, `after==MERGE_HEAD` and `_ait_merge_stop_shaped "$out"`.
  The not-stopped branch's wording is unchanged: still `data_midop`.
- Signal 4: add a `MERGE_HEAD` arm. When `own_merge==1`, call
  `ait_merge_abort_if_ours _ait_data_git …` and print:
  - `aborted` → `aitask: $AIT_PULL_MERGE_ABORTED_SENTINEL - worktree restored, local commits kept`
  - `abort_failed` → `aitask: merge --abort failed - the data worktree is mid-MERGE_HEAD; finish or abort it, or run './ait git-health'` (classifies `data_midop`)
  - `not_ours` → the existing `aitask: the data worktree is mid-MERGE_HEAD; leaving it untouched`
  - then `return 0`. When `own_merge==0`, the current message is unchanged.
    Never auto-merge, and never return 10 on this path.
- Update the five-signal comment on `_task_pull_rebase`: signal 3 names the
  merge predicate, signal 4 becomes "the pull's own kind of state", and signal
  5 names both per-operation rules.

**f. `task_git_pull`:** after the interactive-mode refusal, decide merge mode
from the resolved `mode`. Lower-case it with `tr` (bash 3.2: no `${,,}`):
`""|false|no|off|0` → `own=(--own-merge)`. Any other value passes no flag, so
it fails closed. Pass `${own[@]+"${own[@]}"}` first to `_ait_owned_pull`.
Rewrite the BOUNDS docblock: a stopped merge this pull started **and
recognises** is aborted (never auto-merged); an unrecognised stop is left in
progress as `data_midop` for manual recovery; a `--no-commit` pause (rc 0) is
reported and left alone; a merge started elsewhere is never touched.

**g. `_task_push_classify`:** add an arm right after the `data_midop` arm:
`*"$AIT_PULL_MERGE_ABORTED_SENTINEL"*) echo "merge_aborted"`. It must come
before the `*CONFLICT*` arm, so a conflicted merge is never called a
`rebase_conflict`. **`_task_push_reason_hint`:** add `merge_aborted)` →
"the merge stopped before completing (a conflict, a refused merge commit, or a
failed commit or branch update) and was aborted (nothing left in progress);
local and remote diverge — reconcile with './ait sync', or merge by hand with
plain 'git -C .aitask-data merge @{upstream}'". The hint must not contain the
word "rebase", because the gateway tests assert that no line of ours says it.

`merge_aborted` is reachable only from the gateway, since only `task_git_pull`
passes `--own-merge`. `task_sync` / `task_push` / `aitask_pick_own.sh`'s
`SYNC_FAILED` vocabulary therefore cannot see it and are left unchanged.

### 2. `tests/test_ait_git_gateway_pull.sh` (integration, real dispatcher)

Add one shared helper for "this aborted, and nothing else was lost". It
asserts:
- no wedge;
- `reason=merge_aborted`, with the sentinel present;
- none of our lines contains `rebase`;
- HEAD == HEAD before the pull, so the local commit is still the tip;
- a pre-planted unrelated **unstaged** edit is still on disk, and
  `git -C "$DATA" status --porcelain` shows only that edit, as ` M`;
- `next_commit_rc` is 0.

| test | stop | fixture | precondition asserted on `ERR` |
|---|---|---|---|
| **C** (rewritten) | conflict | `force_conflict`, `-c pull.rebase=false` | `CONFLICT` |
| **L** (rewritten) | `pre-merge-commit` refusal | diverged non-conflict, `--no-rebase` | `refused by test hook` |
| **N** (new) | signing failure | diverged non-conflict; `./ait git -c commit.gpgSign=true -c gpg.program=/bin/false pull --no-rebase` | `failed to write commit object` |
| **O** (new) | branch update rejected after the merge commit | diverged non-conflict; a **one-shot** `reference-transaction` hook that rejects the `prepared` update of `refs/heads/aitask-data` once (marker file), then allows every later update | `update aborted by the reference-transaction hook` |
Every row above uses the shared helper. Test O's one-shot hook is what makes
the helper's `next_commit_rc` meaningful: later ref updates are allowed. The
hook is removed afterwards. Drop Test C's manual `rm -f MERGE_HEAD …`.

The two rows below are **preservation** cases. They use a second shared
helper, "left in place", which asserts:
- `probe_wedge` = `MERGE_HEAD`;
- `reason=data_midop`, with our `mid-MERGE_HEAD; leaving it untouched` line;
- no merge-aborted sentinel;
- the merge is still the one that was there: `MERGE_HEAD` and `ORIG_HEAD` are
  unchanged since the pull returned.

Each case then cleans up with plain `git -C "$DATA" merge --abort`.

| test | case | fixture | precondition asserted on `ERR` |
|---|---|---|---|
| **O-q** (new) | branch update rejected after the merge commit, **under `-q`**: no merge-specific marker, so the stop is left for manual recovery | as O, with `pull -q --no-rebase` | the ref-tx fatal is present **and** `Merge made by` is absent (proves this is the quiet shape) |
| **P** (new, the round-3 reproduction) | **fetch-time** rejection with a foreign merge injected: every evidence gate matches, but no merge-specific marker | diverged; a one-shot `prepared`-phase hook on `refs/remotes/origin/aitask-data` runs `git -c core.hooksPath=/dev/null merge --no-ff --no-commit <new sha> >/dev/null 2>&1`, then rejects the fetch; `./ait git pull --no-rebase` | the ref-tx fatal is present; `ORIG_HEAD` == HEAD before; `MERGE_HEAD` == the `FETCH_HEAD` for-merge SHA (so the evidence gates *would* pass); no `Merge made by` |

- **Test M** (new, deliberate pause): a clean `pull --no-rebase --no-commit`
  exits non-zero through the unverified postcondition. Assert that `MERGE_HEAD`
  is **still present** and that there is no merge-aborted sentinel. Clean up
  with plain `git -C "$DATA" merge --abort`.

### 3. `tests/test_task_push.sh` (unit, fabricated git-dir — the Test 42/46 style)

- **Test 10:** classifier rows: conflict text + `aborted` sentinel →
  `merge_aborted`; the `abort_failed` text → `data_midop`. Hint row:
  `merge_aborted` mentions `was aborted (nothing left in progress)` and has no
  `rebase`.
- **New Test 48 — `ait_merge_abort_if_ours` verdict table.** Plant `ORIG_HEAD`,
  `MERGE_HEAD` and `FETCH_HEAD` in a temp dir, and use stub runners that record
  whether they ran.
  - Ours, abort lands → `aborted`. Ours, abort fails → `abort_failed`.
  - Each of these → `not_ours`, with the runner never run:
    - foreign `ORIG_HEAD`, or missing `ORIG_HEAD`;
    - `MERGE_HEAD` ≠ the `FETCH_HEAD` tip;
    - `FETCH_HEAD` with only `not-for-merge` lines, or missing `FETCH_HEAD`;
    - empty `head_before`;
    - a non-merge state.
  - Two-line octopus `MERGE_HEAD` matching two for-merge lines → `aborted`;
    the same lines reordered → `not_ours`.
- **New Test 49 — predicate and cleanup seam.**
  - `_ait_merge_stop_shaped` table. Returns 0 for the probed output of each
    family, verbatim:
    - conflict;
    - `Not committing merge`;
    - gpg + `failed to write commit object`;
    - `Merge made by` + ref-tx fatal.

    Returns 1 for:
    - **the ref-tx fatal alone** (the `-q` shape and the fetch-time shape);
    - `index.lock` contention;
    - `could not resolve host`;
    - `would be overwritten by merge`;
    - an **unlisted** fatal (for example `fatal: cannot lock ref 'HEAD'`);
    - empty output.
  - Cleanup with `own_merge=1` + matching evidence → aborted, with the
    sentinel, for each family. This uses a stubbed `_ait_data_git` that removes
    `MERGE_HEAD`.
  - **Unrecognised stop** (`own_merge=1` with matching evidence) for each of:
    an unlisted fatal; the ref-tx fatal alone. Each is left untouched,
    reported `mid-MERGE_HEAD` / `data_midop`, and the runner is not run. This
    pins the documented manual-recovery limit and the round-3 rule.
  - Each of these is left untouched:
    - the same state with `own_merge=0` (the existing 46m stays the control);
    - `own_merge=1` + conflict output + foreign `ORIG_HEAD`;
    - `own_merge=1` + a pre-existing `MERGE_HEAD` (`before` set).

### 4. `website/content/docs/commands/sync.md` (`## ait git pull`)

Current-state wording only. Remove every unconditional "always cleans up"
claim:

- Intro paragraph: replace "it never leaves the data worktree stuck
  mid-rebase" with a qualified statement. A rebase it started that stops is
  auto-merged or aborted. A merge it started that stops in a way it recognises
  is aborted. Anything it cannot attribute to its own pull, or does not
  recognise, is left in place and reported. "A rebase **or merge** that some
  other session started is never touched." Add `merge_aborted` to the reason
  list.
- Replace the bullet "A stopped merge is left to you" with "A stopped merge
  is aborted when it is recognised". With `pull.rebase=false` /
  `--no-rebase`, a merge this pull started is aborted, leaving nothing in
  progress and reporting `merge_aborted`, when it stops because:
  - it hit a conflict;
  - a hook refused the merge commit;
  - the merge commit could not be written (for example, signing failed);
  - or the branch could not be updated after the commit.

  It is never auto-merged. **If git reports the stop in a way the gateway does
  not recognise, the merge is left in progress and reported as `data_midop`.
  Recover by hand with `./ait git merge --abort`** (or finish it). One example:
  with `-q`, a branch update that fails after the merge commit was written
  prints nothing that identifies it as this pull's merge, so it is left in
  place. A merge
  paused with `--no-commit` is left as it is and reported as unverified.
- Widen "Resolving a rebase conflict by hand" to cover both: plain
  `git -C .aitask-data pull --rebase` / `--no-rebase`.
- Run `python3 check_links.py --build` (in `website/`).

## Verification

```bash
bash tests/test_ait_git_gateway_pull.sh
bash tests/test_task_push.sh
bash tests/test_task_git.sh          # gateway parser/guard neighbours
shellcheck .aitask-scripts/lib/task_utils.sh
cd website && python3 check_links.py --build
```

Red proof: run the edited tests once against the unmodified lib, and the new
abort assertions in Tests C, L, N, O, 48 and 49 fail. That is today's bound:
`MERGE_HEAD` survives and the reason is `data_midop`. Then run them against
the fixed lib. The preservation cases (Tests M, O-q and P, and the
unrecognised-stop rows) pass on both, because they pin unchanged behaviour.
Then a **mutant check** for Test P: temporarily add the ref-tx fatal back to
`_ait_merge_stop_shaped` in a scratch copy of the lib (never the shared
tree), run Test P against it, and see it fail by aborting the injected merge.
This proves Test P actually guards the round-3 rule.

Step 9 (Post-Implementation): current-branch mode, no merge. Archive via
`aitask_archive.sh 2064` once `ait gates run` has recorded `risk_evaluated`.

## Risk

### Code-health risk: low
- A new arm in the shared `_task_push_classify`. It is keyed only on a
  framework-owned sentinel that no other path emits, and the Test 10 table pins
  its position · severity: low · → mitigation: None (covered by the plan's Test 10 rows)
- One more branch in a load-bearing pull path. The workflow pull never passes
  `--own-merge`, so its behaviour is unchanged (Test 46m stays the control) ·
  severity: low · → mitigation: None

### Goal-achievement risk: medium
- Recognising a stopped merge is a list of four probed, merge-specific git
  message families, and it is **not exhaustive**. Two review rounds each found
  a family the previous list missed. A third round showed that a generic fatal
  (the ref-transaction line, which fetch also prints) is not merge evidence, so
  `-q` branch-update stops stay unrecognised. An unrecognised stop fails closed: the merge is left in
  place, reported as `data_midop`, and needs a manual `./ait git merge --abort`.
  The user decided this, and the docs state it (the trace2 alternative is out of
  scope) · severity: medium · → mitigation: None (documented bound; Test 49's unrecognised-stop row pins the fail-closed side)
- `ORIG_HEAD` is read as a file. Under a reftable ref backend it is not a
  file, so the merge fails closed and is left in place: today's behaviour,
  never a wrong abort · severity: low · → mitigation: None
- A merge-mode frontmatter-only conflict is aborted rather than auto-merged,
  unlike the rebase path. The task allows abort-only, and the docs state it ·
  severity: low · → mitigation: None
