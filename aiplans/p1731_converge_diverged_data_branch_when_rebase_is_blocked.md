---
Task: t1731_converge_diverged_data_branch_when_rebase_is_blocked.md
Base branch: main
Output branch: main
plan_verified: []
---

# t1731 — converge a diverged data branch with a guarded merge when the rebase is blocked

### Pre-phase (risk mitigations)

1. **[guarded_merge_truth_table]** — *before any `aitask_sync.sh` edit.* Write
   `tests/test_sync_guarded_merge.sh` as the **specification**.

   **Every cell asserts two separate things:**
   - **(a) guard coverage.** The refusal *slug* the guard is supposed to fire,
     read from stderr as `Guarded merge not possible (<slug>): …`, or the
     `MERGED` verdict.
   - **(b) end-to-end preservation.** The first-line token, `HEAD` (moved to
     a two-parent merge, or equal to the pre-run SHA), and protected / ignored
     bytes (sha256 equal to a pre-run snapshot, still ` M` / `??`).

   These are kept distinct on purpose. Several guards have an independent git
   backstop — `merge --ff-only` itself refuses to overwrite a dirty or
   untracked file — so (b) can stay green with the guard removed. Only (a)
   proves the guard.

   Run it against the unmodified script and record which cells are red: every
   `MERGED` cell must be, and deferral cells may already be green on (b).

   Cells (slug in parentheses):
   - **AC cells** (see **Tests**).
   - **Rename** — local `git mv t30_gamma.md t31_x.md`, pc2 edits
     `t30_gamma.md` → deferred (`sides_overlap`). Pins `--no-renames`.
   - **Directory/file, merge direction** — local adds `aitasks/t40/x.md`, pc2
     adds a file `aitasks/t40` → deferred (`merge_conflict`).
   - **Directory/file, protected direction** — protected untracked
     `aiplans/p10_d` (a file), pc2 adds `aiplans/p10_d/y.md` → deferred
     (`protected_written`; the prefix rule).
   - **Case fold** — protected untracked `aiplans/p10_Case.md`, pc2 adds
     `aiplans/p10_case.md` → deferred (`protected_written`; the fold rule).
     There is no git backstop on a case-sensitive filesystem.
   - **Ignored, present at prepare** — local `aitasks/metadata/x.local.json`
     exists and pc2 force-adds that path → deferred (`ignored_written`), local
     bytes unchanged.
   - **Ignored, race** — the `pre_guarded_ff` seam creates local
     `aitasks/metadata/x.local.json` (pc2 force-added that path) *after*
     prepare's scan → deferred (`ff_refused`), `HEAD` unchanged (== pre-run
     SHA), local bytes preserved. This is the case only
     `--no-overwrite-ignore` stops; git's default silently overwrites ignored
     files.
   - **Criss-cross** — two merge bases (pc2 and local each merge the other's
     pre-advance tip) → deferred (`multiple_merge_bases`).
   - **Moving refs** — the `pre_guarded_ff` seam commits on the data branch
     between prepare and fast-forward → deferred (`ff_refused`), `HEAD` == the
     seam's commit, never `C`.
   - **Hostile path** — a protected untracked path containing a newline, and
     pc2 creating that same path → deferred (`protected_written`).
   - **Slug-completeness scan** — the test scans `_gm_refuse "<slug>"` literals
     from the script and asserts each has a driving cell or an explicit
     `UNREACHABLE` entry with a one-line justification (`rev_unresolved`,
     `unknown_state`). It also runs a reverse check (every driven slug exists in
     source), so the scan cannot pass vacuously. This mirrors t1725_3's
     protect-paths harness.

2. **[reshaped_fixtures_assert_shape]** — *before reshaping any existing test.*
   Add `advance_remote_overlapping <tmpdir>` to
   `test_sync_deferral_and_quarantine.sh` (pc2 appends to both
   `t20_beta.md` and `t30_gamma.md`). Every flipped test switched to it asserts
   its shape as well as its verdict:
   - the overlap is really present — `t20_beta.md` is in both
     `diff --name-only <mb> HEAD` and `<mb> @{u}` after the run's fetch;
   - stderr names the `sides_overlap` slug, so the test cannot keep passing by
     deferring for some other reason.

   Where it applies:
   - **Switched to the helper:** Tests 1, 1b, 31B, 33, 33B, 33C, 33D.
   - **Test 19:** `install_racing_pre_push` gains a path argument and the racer
     uses `t20_beta.md`. Same assertions.
   - **The new truth-table overlap cell:** same assertions.
   - **Comments:** Test 1's and 1b's comments say why the overlap is
     load-bearing.

## Context

`ait sync` defers forever on the normal shape of a multi-agent box: the data
branch is **diverged** (`local_ahead > 0` and `remote_ahead > 0`) and some live
session holds a modified **tracked** task file.

- `_rebase_blocked` rule 3 (`tracked AND local_ahead > 0`, `aitask_sync.sh`
  ~1463) blocks, because `git pull --rebase` refuses on *any* unstaged tracked
  change.
- The t1599_3 protection is exactly what stops convergence.
- `DEFERRED:` is benign, so nothing escalates.

All three live measurements were diverged, never behind-only, so t1725_3's
fast-forward never fired: 6/8, 21/39, and 24/26. This session's own claim
printed "unstaged changes blocking rebase".

A merge refuses only when it would **overwrite** a dirty file, which is a
strictly weaker precondition. So when the rebase is blocked and a merge is
provably safe, converge with a merge commit and push. Otherwise, defer exactly
as today.

## Decisions (user-confirmed at planning)

- **Merge commits on `aitask-data` are accepted, including routinely.**
  - A rebase stays preferred whenever `_rebase_blocked` allows it; the merge is
    used **only** when the rebase is blocked.
  - Precedent: `87b49bcfa`, `db7f9b1d0`.
- **Protected files stay byte-for-byte identical, uncommitted and unstaged.**
  - Nothing here commits, stages or writes a protected path.
  - Any failed check defers as today.
  - A successful convergence must push; a test asserts it.
- **`task_data_converge` (`lib/task_utils.sh` ~1554) stays fast-forward-only**
  (t1658_1).
  - Its "reconcile with ait syncer / ./ait sync" hints become truthful for the
    disjoint case. They offer a **recovery attempt, not a guarantee**:
    overlapping changes still defer and need intervention. The docs say so.
  - No `task_utils.sh` change.
- **Follow-up task (user-approved), filed right after approval:** syncer's
  `_main_pull_worker` (`syncer/syncer_app.py` ~2326) refuses the code-branch
  pull on any dirty status, though `pull --ff-only` refuses only on an
  overwrite. (Inbox note point 4.)
- **Outcome token: new bare status `MERGED`.**
  - Emitted only when a guarded merge landed **and** the push succeeded.
  - Behind-only keeps t1725_3's ff → `PULLED` (AC 4).
  - The `DEFERRED:` wire is unchanged.

## Coordination with in-flight work (gate before editing)

- **t1725_4** (Implementing, plan approved 2026-09-10 11:56) holds
  **uncommitted** hunks in `aitask_sync.sh`: header ~37-41, the pane helpers
  after `_sync_test_seam`, `_protect`, `_holder_action`, `_commit_group`, and
  `show_help` ~154-157.
- It also holds an untracked `tests/test_sync_holder_pane_live.sh`. Its
  `new_fixture` (~123-131) is the disjoint diverged shape, so these cases flip:
  S1, S1a, S1c, S2, S3, E1a.
  - **Right after approval,** send t1725_4 a note (`/aitask-note`): make
    `new_fixture` overlap-shaped (pc2 also edits `t20_beta.md`) or
    incoming-shaped.
  - **Rebase check before editing.** If t1725_4 has committed, re-read the
    landed `aitask_sync.sh` and re-derive the anchors. If it landed with a
    disjoint fixture, reshape it here under pre-phase 2.
- **Files this task does not touch** (both are dirty from t1725_4):
  `tests/lib/sync_fixture.sh` and `tests/test_sync_protect_paths.sh`.
  - New helpers live in the new test file.
  - `MERGED` cannot reach protect-paths, since no driver advances the remote.
    Add it to `RECOGNISED` only if t1725_4 has committed that file by Step 8.
- **Never write the shared `aitask_sync.sh` for an experiment.** Probes and
  mutants run only in isolated copies (see **Mutation controls**). Restoring a
  backup would erase edits another session made in the meantime, and anyone
  running sync in between would execute a broken script.
- **t1747_2 / t1747_3** touch `task_automerge.sh` and `do_pull_rebase`; not
  edited here.

## Design

Anchors are current-tree approximations; re-derive them, since the file moves.

### Wiring

`main` (~1834) today runs `_rebase_blocked` → `_emit_protected_deferral;
exit 0`. That becomes:

```
if (( ${#PROT_REASON[@]} )) && _rebase_blocked "$local_ahead" "$remote_ahead"; then
    gm_rc=0; _converge_by_guarded_merge "$local_ahead" "$remote_ahead" || gm_rc=$?
    case $gm_rc in
        0) did_merge=true ;;                     # HEAD advanced to the merge; skip Step 7
        1) _emit_protected_deferral
           iwarn "Guarded merge not possible ($GM_SLUG): $GM_REFUSAL"; exit 0 ;;
        *) exit 1 ;;                             # ERROR:<…> already emitted
    esac
fi
```

- **`do_push` retry (~1734):** the same three-way branch after its re-gate, on
  `retry_local` / `retry_remote`.
  - 0 → push again.
  - 1 → deferral, `return 2`.
  - 2 → `return 1`.
- **Step 9:** `did_merge && did_push` → `batch_out "MERGED"`, checked first.
  It is exclusive with `_PULL_AUTOMERGED`.
- **Merge landed, push did not:** `do_push`'s own token stands, and stderr names
  the local merge SHA ("merged locally, not yet published").

### Refusal vocabulary (stderr only, never the wire)

`_gm_refuse <slug> <detail>` sets `GM_SLUG` / `GM_REFUSAL` and returns 1. The
closed slug set:

- `not_diverged`
- `unknown_state`
- `rev_unresolved`
- `multiple_merge_bases`
- `sides_overlap`
- `merge_conflict`
- `protected_written`
- `ignored_written`
- `ff_refused`

One distinct slug per guard is what makes guard coverage observable apart from
git's own backstops.

### `_guarded_merge_prepare <local_ahead> <remote_ahead>` — decide, mutate nothing

Each check fails closed.

1. `local_ahead > 0 && remote_ahead > 0`, else `not_diverged`.
2. No `PROT_STATE == unknown`, else `unknown_state`.
3. **Pin the inputs once:** `GM_H=$(task_git rev-parse --verify HEAD)` and
   `GM_U=$(task_git rev-parse --verify '@{u}')` (`rev_unresolved` on failure).
   Every later step takes SHAs only.
4. `merge-base --all H U` must yield exactly one line → `B`. Otherwise
   `multiple_merge_bases`.
5. **Policy — disjoint sides:**
   - `LOCAL_SIDE = diff -z --no-renames --name-only B H`
   - `REMOTE_SIDE = … B U`

   Both are NUL-safe associative arrays built in `_load_incoming`'s
   **exit-free mktemp → read → rm window** (no trap). A non-empty
   intersection → `sides_overlap`.
6. **Proof:** `GM_TREE=$(_ait_data_git merge-tree --write-tree --no-messages H
   U)`. It must exit 0 and yield a bare object id, else `merge_conflict`.
   - It writes only loose objects.
   - `_ait_data_git` has no `die()` path.
7. **Protection is checked against the paths actually written:**
   `WRITTEN = diff -z --no-renames --name-only H GM_TREE`. It is
   `protected_written` if any protected P (tracked or untracked) and any W in
   `WRITTEN` satisfy any of:
   - `P == W`
   - W under `P/`, or P under `W/`
   - either of the above after case-folding both (`${x,,}`)
8. **Ignored files, present now:** `WRITTEN` collides by the same match with
   `ls-files -o -i --exclude-standard -z` → `ignored_written`.
   - The data branch ignores `aitasks/new/`, `userconfig.yaml`, `*.local.json`,
     `profiles/local/`, `applink_sessions/` and `chatlink_sessions/`.
   - This check is early and gives a specific reason. It **cannot** cover a
     file created after it runs; the fast-forward flag below does.

### `_converge_by_guarded_merge`

- Prepare; not eligible → return 1.
- `C=$(_ait_data_git commit-tree "$GM_TREE" -p "$GM_H" -p "$GM_U" -m "ait:
  Merge <U:0:12> into aitask-data — rebase blocked by N protected file(s)")`.
  - Its tree is exactly `GM_TREE`.
  - On failure → `ERROR:guarded_merge_failed`, return 2 (no ref moved).
- `_sync_test_seam pre_guarded_ff`.
- **Advance:**

  ```
  ff_rc=0
  ff_err="$(task_git merge --ff-only --no-autostash --no-overwrite-ignore --quiet "$C" 2>&1)" || ff_rc=$?
  ```

  This runs inside `$( )`, so a `die()` stays confined.
  - `--ff-only` checks everything before writing and refuses:
    - to overwrite a dirty or untracked file;
    - if HEAD moved off `GM_H`.

    It leaves unrelated staged entries alone.
  - `--no-autostash` defeats `merge.autoStash=true`.
  - `--no-overwrite-ignore` refuses to replace an ignored file, including one
    created after prepare. git's default is to overwrite silently.
  - There is no `MERGE_HEAD`, and never an `--abort`.
  - On refusal, HEAD is unchanged → `_gm_refuse ff_refused "$ff_err"`,
    return 1 (a deferral).
- **Verify:** `rev-parse HEAD == C` and an empty
  `diff --quiet GM_H C -- <protected…>`.
  - A mismatch → `ERROR:guarded_merge_unverified`, return 2, no push.
  - There is no byte-hash check; the holder is live, so it would be racy.
- **Success** → stderr `merged <C>; N protected file(s) left uncommitted` →
  return 0.

### Adjacent one-flag fix (same gate, same failure class)

`_load_incoming` (~1430) is missing `--no-renames`. An incoming rename X→Y lists
only Y, so rule 4 misses a protected X and the run reports
`ERROR:pull_rebase_failed` instead of deferring. Add the flag, pinned by a
truth-table cell.

## Files

| File | Change |
|---|---|
| `.aitask-scripts/aitask_sync.sh` | `_gm_refuse`, `_load_merge_sides`, `_guarded_merge_prepare`, `_converge_by_guarded_merge`, `pre_guarded_ff` seam (documented in the seam list); main + do_push wiring; `MERGED` in the header protocol block and `show_help`; rule-3 / gate comments point at the merge; `--no-renames` in `_load_incoming` |
| `.aitask-scripts/lib/sync_action_runner.py` | `STATUS_MERGED = "MERGED"` in the bare-token list (~330) |
| `.aitask-scripts/syncer/syncer_app.py` (~2262), `board/aitask_board.py` (~12312) | `MERGED` → information notify "Sync: Merged — protected files left uncommitted" |
| `tests/test_sync_guarded_merge.sh` | **new** (pre-phase 1) |
| `tests/test_sync_rebase_gate.sh` | verdicts `blocked\|open\|merged`; line 131 → `merged`; new overlap cell and incoming-rename cell → `blocked` |
| `tests/test_sync_deferral_and_quarantine.sh` | pre-phase 2 reshapes |
| `tests/test_sync_action_runner.py` | `MERGED` parses (the token-contract scan also covers it) |
| `website/content/docs/commands/sync.md` | `MERGED` row; restate "Skipped files can block the later rebase" to current behavior incl. the recovery-attempt-not-guarantee wording |

## Tests (AC cells in `tests/test_sync_guarded_merge.sh`)

The file uses top-level in-process counters and no subshell test bodies, or
opts into `assert_counters_init` / `assert_counters_load` (t1207).

Base fixture: `setup_repo`, `plant_lock 10 live`, a tracked edit to
`t10_alpha.md`, a `t20_beta.md` edit (an unlocked local commit), and a pc2
advance.

1. **AC1 — converges and pushes.** pc2 touches `t30_gamma.md`. Assert:
   - `MERGED`
   - both `rev-list --count` directions are 0 after a fetch
   - the remote ref == local HEAD
   - HEAD has two parents
   - `t10_alpha.md` sha256 unchanged and still ` M`
   - `t10_alpha.md` is in no commit since the pre-run HEAD, nor in
     `diff --cached`
   - `from pc2` arrived
2. **AC2 — incoming touches t10** → `DEFERRED:protected_dirty` (slug
   `sides_overlap` or `protected_written`, asserted), HEAD unchanged.
3. **AC3 — overlap** → deferred (`sides_overlap`), HEAD unchanged.
4. **AC4 — behind-only** → `PULLED`, not `MERGED`; HEAD has one parent.
5. **AC5 — mid-rebase** (`rebase-merge` sentinel) → `DEFERRED:worktree_wedged`,
   HEAD unchanged, and no slug line (the guarded path never ran).
6. **AC6** — no assertion anywhere expects a protected path committed, staged
   or modified.
7. **Retry path** — a pre-push racer touches t30 → `MERGED`, remote converged,
   protected bytes identical.

### Mutation controls — isolated copies only, never the shared script

**Procedure, per mutant:**
1. Copy `ait`, `.aitask-scripts/` and `tests/` from the working tree into a
   fresh scratchpad directory `$SCRATCH/mut/<mutant>/`.
2. Apply the mutant to **that copy's** `aitask_sync.sh`.
3. **Assert it landed:** grep the mutated line in the copy, and confirm that a
   fixture built from it carries the mutation. `setup_repo` copies
   `$PROJECT_DIR/.aitask-scripts`, and `PROJECT_DIR` resolves to the copy.
4. Run the copy's `tests/test_sync_guarded_merge.sh`.
5. Delete the copy.

The shared `.aitask-scripts/aitask_sync.sh` is never written for an experiment,
so there is never anything to restore.

**What must go red.** Guard coverage is judged on the **slug** assertion.
End-to-end preservation is reported separately and is allowed to stay green
where git backstops the guard.

| Mutant | Cell | Slug assertion | End-to-end (b) |
|---|---|---|---|
| side sets without `--no-renames` | rename | must go red | may stay green |
| ignore merge-tree's exit status | D/F merge direction | must go red | **must go red** (conflicted tree merged) |
| drop the prefix rule | D/F protected direction | must go red | may stay green (ff refuses untracked overwrite) |
| drop the case fold | case fold | must go red | **must go red** (no backstop on Linux) |
| drop the ignored-file scan | ignored, present | must go red | may stay green (`--no-overwrite-ignore` backstop) |
| drop `--no-overwrite-ignore` | ignored, race | n/a (`MERGED`) | **must go red** (bytes replaced) |
| drop the disjointness check | AC3 | must go red | **must go red** (overlap merged) |
| drop the WRITTEN-membership check | AC2 | must go red | may stay green (ff refuses dirty overwrite) |
| drop the merge-base count | criss-cross | must go red | may stay green |

SHA pinning has no mutant that end-to-end tests can kill: the fast-forward's
own HEAD check refuses either way. It is recorded as **coverage by
construction** (the moving-refs cell pins the outcome) and not claimed as
mutant-killed. Record every observed outcome in the Implementation notes.

### Post-phase (risk mitigations)

1. **[isolated_commit_verification]** — *at Step 8, around the code commit.*
   - **If t1725_4's hunks are still uncommitted in `aitask_sync.sh`:** build
     the commit from a **whitelist of this task's own hunks**.
     1. Build a blob from `git show HEAD:<path>` plus our hunks, then stage it
        with `git hash-object -w` and `git update-index --cacheinfo`. This
        leaves their working-tree edits intact.
     2. Commit that path along with our other files.
     3. `git worktree add --detach <scratch>/wt <sha>`, then run the sync
        suites there: `test_sync_guarded_merge`, `test_sync_rebase_gate`,
        `test_sync_deferral_and_quarantine`, `test_sync`,
        `test_sync_auto_commit_scoping`, and `test_sync_action_runner.py`.
     4. Run the same suites at `<sha>^` as a control, and attribute only the
        delta.
     5. Remove the worktree.
   - **Otherwise:** a normal path-scoped commit, and `git show --stat <sha>`
     must list only this task's files.

2. **[live_eligibility_probe]** — *after tests pass, before Step 8 review.* Run
   prepare's computations by hand against the **real** `.aitask-data`:
   - pinned SHAs
   - merge-base count
   - side-set sizes and their intersection
   - merge-tree cleanliness (loose objects only; no ref moves)
   - `WRITTEN` ∩ protected and ∩ ignored

   Record the verdict and slug in the plan. A real `./ait sync` would create
   and push a merge on the shared branch, so it is offered separately and never
   run without confirmation.

## Verification

```bash
bash tests/test_sync_guarded_merge.sh
bash tests/test_sync_rebase_gate.sh
bash tests/test_sync_deferral_and_quarantine.sh
bash tests/test_sync.sh
bash tests/test_sync_protect_paths.sh
bash tests/test_sync_auto_commit_scoping.sh
bash tests/test_sync_branch_mode_automerge.sh
bash tests/test_metadata_commit_seam.sh
bash tests/test_sync_holder_pane_live.sh   # t1725_4's; passes once new_fixture is overlap-shaped
set -o pipefail; bash tests/run_all_python_tests.sh --test-dir tests   # verdict = LAST line
shellcheck .aitask-scripts/aitask_sync.sh
cd website && python3 check_links.py --build
```

## Risk

### Code-health risk: high
- The eligibility check is a new **fail-open surface over user-controlled
  bytes**: renames, directory/file shapes, case folding, ignored files
  (including ones created after the scan), criss-cross history, and moving
  refs. t1725_3 found five instances of this class; this plan's reviews found
  seven more before any code existed · severity: medium (residual — addressed
  by inline pre-phase guarded_merge_truth_table: per-guard slugs, isolated
  mutants, and the `--no-overwrite-ignore` race cell) · → mitigation: inline
  pre-phase guarded_merge_truth_table
- **Concurrent uncommitted edits in the same file.** t1725_4's hunks sit in
  `aitask_sync.sh`, and its live test asserts the deferral this task removes.
  A path-scoped commit would carry their hunks, and an in-place mutate-and-
  restore could erase them · severity: medium (residual — addressed by inline
  post-phase isolated_commit_verification, the isolated-copy mutation rule, and
  the note to t1725_4) · → mitigation: inline post-phase
  isolated_commit_verification
- **Nine existing pins flip** (truth-table 131; deferral Tests 1, 1b, 19, 31B,
  33, 33B, 33C, 33D). A reshaped test can defer for the wrong reason ·
  severity: low (residual — addressed by inline pre-phase
  reshaped_fixtures_assert_shape) · → mitigation: inline pre-phase
  reshaped_fixtures_assert_shape
- A new wire token across the runner and two TUIs, where a missed consumer
  renders an error. Bounded by `test_every_emitted_token_is_recognised` ·
  severity: low · → mitigation: none (covered by the existing scan)

### Goal-achievement risk: medium
- The practical convergence rate is unknown. If both sides routinely touch the
  same file, the disjointness policy refuses and deferral stays common. One
  live sample so far (16 vs 13, disjoint) · severity: medium (residual —
  measured, not reduced, by inline post-phase live_eligibility_probe) ·
  → mitigation: inline post-phase live_eligibility_probe
- Merging on the push-retry path goes slightly beyond the ACs. It is needed
  because a rejected push in the same shape would re-create the deadlock ·
  severity: low · → mitigation: none

### Planned mitigations
- timing: pre-phase | name: guarded_merge_truth_table | type: test | priority: high | effort: medium | inline_risk: low | added_complexity: low | addresses: code-health 1 (fail-open eligibility surface) | desc: spec-first cell table with per-guard refusal slugs (ACs, rename, D/F both directions, case fold, ignored present + post-scan race, criss-cross, moving refs, hostile path), slug-completeness scan, and mutation controls run only in isolated scratch copies
- timing: pre-phase | name: reshaped_fixtures_assert_shape | type: test | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: code-health 3 (flipped pins deferring for the wrong reason) | desc: every reshaped deferral test asserts the overlap is present in both merge-base sides and that stderr names the sides_overlap slug
- timing: post-phase | name: isolated_commit_verification | type: test | priority: high | effort: low | inline_risk: low | added_complexity: low | addresses: code-health 2 (t1725_4's uncommitted hunks in the same file) | desc: whitelist-of-own-hunks commit when t1725_4 is unlanded, verified in a detached worktree against a parent-commit control
- timing: post-phase | name: live_eligibility_probe | type: test | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: goal-achievement 1 (unknown practical convergence rate) | desc: read-only run of the eligibility computations against the real aitask-data, verdict and slug recorded in the plan

**Post-inline reassessment** (single pass): the phases pin each guard and bound
the concurrent-edit hazard, but none shrinks the blast radius. The gate is
still rewritten at two call sites, and nine pins still change. Code-health
therefore stays **high**. The probe measures the convergence rate rather than
improving it, so goal-achievement stays **medium**.

## Upstream defects noted (for Step 8b, not fixed here)

- **`do_pull_rebase` autostash** — `aitask_sync.sh` (~1555): `pull --rebase`
  runs without `--no-autostash`, so a user's `rebase.autoStash=true` stashes
  and re-applies protected files. t1747_2/3 own `do_pull_rebase`.
- **Ignored files overwritten on the existing paths** — `aitask_sync.sh` main
  Step 7: the existing behind-only `merge --ff-only --quiet @{u}` and the
  rebase path both silently overwrite ignored files (git's default, confirmed
  in `git merge -h` / the man page). Same class as the race cell above, on
  t1725_3's fast-forward.
- **Test fixture inherits global git config** — `tests/lib/sync_fixture.sh`
  (172-183): `run_sync` inherits the developer's global git config (no
  `GIT_CONFIG_GLOBAL`), so autostash-type config leaks into every sync test.

## Implementation notes (2026-09-10)

- **Pre-phase 1 baseline.** `tests/test_sync_guarded_merge.sh` was run against
  the unmodified script at `da20ffd80`: 100 passed, 37 failed. All 37 failures
  were expected reds:
  - both `MERGED` cells (AC1 and retry), which still deferred;
  - every slug assertion, because no guard existed yet;
  - both "seam fired" checks, because `pre_guarded_ff` did not exist;
  - the slug scan.

  Every end-to-end (b) deferral assertion was already green, and AC4 and AC5
  passed unchanged. So the table specified the change rather than transcribing
  it.
- **The coordination premise changed mid-task.** t1725_4 landed (`76a113510`)
  and was archived between planning and the note being sent. The note
  (`2026-09-10T12:54:30Z.ed0c9589…`) was appended to the *archived* task and
  returned `LIVE_NONE:unlocked`, so it will never be read. This task therefore
  reshaped `tests/test_sync_holder_pane_live.sh`'s `advance_remote` itself, as
  the plan's "if it landed with a disjoint fixture" branch required.
  - No foreign uncommitted hunks remain in any target file, so post-phase 1
    takes its "otherwise" branch: a plain path-scoped commit, checked with
    `--stat`.
  - `ait note` accepted an archived target without warning. That is noted for
    Step 8b.
- **Deviation from pre-phase 2 — Test 1b.** Switching 1b to the overlap helper
  would have made it an exact duplicate of Test 1. Instead 1b keeps 1a's
  position and asserts:
  - the verdict is `MERGED`;
  - HEAD has two parents;
  - the protected edit is still ` M`.

  Paired with 1a it still proves the gate discriminates on tree state: 1a
  rebases, 1b cannot and merges. Test 1 is the overlapping cell that defers.
- **Deferral-file survey.** Of the tests the critique did not list:
  - Test 30 (a deferring run leaves no temp file) used the disjoint shape. It
    would have kept passing while no longer testing a deferral, so it is
    reshaped to the overlap.
  - Test 36 stays as is: local_ahead is 0 and the incoming commit touches t10,
    so rule 4 blocks and the guard declines with `not_diverged`.
  - Tests 27, 28 and 29 are unaffected. Test 28's retry fetch fails before the
    gate runs.
- **Where the refusal line goes.** `iwarn` is silent in `--batch`, so the
  refusal line is written to stderr directly. That is the same channel the
  sweep report and the seam banner use.
- **Verification results (before the first review).**

  | Check | Result |
  |---|---|
  | `test_sync_guarded_merge` | 147/147 |
  | `test_sync_rebase_gate` | 38/38 |
  | `test_sync_deferral_and_quarantine` | 124/124 |
  | `test_sync` | 42/42 |
  | `test_sync_protect_paths` | 31/31 |
  | `test_sync_auto_commit_scoping` | 38/38 |
  | `test_sync_holder_pane_live` | 51/51 |
  | `test_sync_branch_mode_automerge` | rc 0 |
  | `test_metadata_commit_seam` | rc 0 |
  | Python suite (last line) | `PYTHON SUITE: PASSED (runner=pytest, exit=0)` |
  | shellcheck | only the pre-existing SC1091 infos on the unchanged `source` lines; `-e SC1091` gives rc 0 |
  | `check_links.py --build` | PASSED |
- **Mutation controls.** Every mutant ran in an isolated scratchpad copy of
  `ait`, `.aitask-scripts/` and `tests/`. The mutator asserted that each
  replacement matched exactly as often as expected, and the unmutated control
  copy passed 147/147.

  | Mutant | Cell | (a) slug | (b) end-to-end |
  |---|---|---|---|
  | side sets without `--no-renames` | rename | red | red (`MERGED`) |
  | ignore merge-tree's exit status | D/F merge | red | red (`MERGED`) |
  | drop the prefix rule | D/F protected | red (`ff_refused`) | green — the fast-forward refuses anyway |
  | drop the case fold | case fold | red | red (`MERGED`) |
  | drop the ignored-file scan | ignored, present | red (`ff_refused`) | green — `--no-overwrite-ignore` refuses anyway |
  | drop `--no-overwrite-ignore` | ignored, race | red | red — the ignored file's bytes were replaced and committed |
  | drop the disjointness check | AC3, and rename | red | red (`MERGED`) |
  | drop the WRITTEN-membership check | AC2, D/F protected, hostile | red (`ff_refused`) | green on AC2 — the fast-forward refuses anyway (case fold went fully red) |
  | drop the merge-base count | criss-cross | red (`sides_overlap`) | green |

  SHA pinning is coverage by construction; no mutant was run for it.
- **A false alarm in the harness.** Its closing check reported 0 occurrences of
  the fast-forward flag in the shared script. Direct inspection showed the flag
  present on the fast-forward line and no mutant marker anywhere. The count had
  used a basic regex containing `$c`, which found nothing; `grep -cF` with the
  same text returns 1. No shared file was written by the experiment.
- **Live eligibility probe.** As of its last fetch, the real `aitask-data`
  branch was ahead-only (local_ahead=1, remote_ahead=0), so the guard would
  answer `not_diverged` and the guarded merge would not run at all. No
  convergence-rate measurement was possible. Goal-achievement risk 1 is
  therefore still **unmeasured**. A real `./ait sync` taken while the branch is
  diverged is what would measure it.

## Step 9

Current-branch mode, so there is no merge. Commit the code per post-phase 1,
then plans and tasks through `aitask_task_commit.sh`. Then archive, then push.

## Post-Review Changes

### Change Request 1 (2026-09-10 20:48)
- **Requested by user:** two gaps in the reshaped deferral fixtures, both
  confirmed against the file.
  - Test 30 discarded sync's stdout, stderr and exit status and asserted only
    that the private TMPDIR was empty. An early error, or a run that never
    deferred, would pass its "a deferring run leaves no temp file" check
    vacuously.
  - Tests 33B–33D switched to the overlapping advance without calling
    `assert_deferred_on_overlap`, although Test 33 does. The approved
    `reshaped_fixtures_assert_shape` mitigation requires every reshaped fixture
    to prove both the overlap and its refusal reason.

  This was an incomplete verification mitigation, not an observed runtime
  failure.
- **Changes made:**
  - Test 30 now captures the status line, stderr (into the fixture's
    `sync_stderr`) and the exit status. It asserts rc 0, a
    `DEFERRED:protected_dirty` first line and `assert_deferred_on_overlap`, and
    keeps its private-TMPDIR leftover check.
  - Tests 33B, 33C and 33D each call `assert_deferred_on_overlap` right after
    reading their wire row.

  The reshaped set now proves its shape uniformly: Tests 1, 19, 30, 31B, 33,
  33B, 33C, 33D and the truth table's overlap cell. Test 1b is the recorded
  exception, and it asserts `MERGED` instead.
- **Files affected:** `tests/test_sync_deferral_and_quarantine.sh`
- **Verification.**
  - The deferral suite passes 138/138. That is exactly the expected rise from
    124: Test 30 adds 5 assertions, and 33B, 33C and 33D add 3 each. The new
    assertions demonstrably executed.
  - **Negative control, in an isolated scratch copy.** Test 30 and Test 33B
    were swapped back to the plain disjoint advance. The run then failed with 9
    failures:
    - Test 30 got `MERGED` where the deferral was expected;
    - both tests' `sides_overlap` and fixture-shape assertions failed;
    - Test 33B's wire-row assertions failed.

    Test 30's "exits 0" and leftover-file checks still passed, which is
    correct: the merge path exits 0 and cleans up after itself. Those two do
    not discriminate on their own; the new deferral and overlap assertions are
    what do.

## Final Implementation Notes

- **Actual work done:**
  - **`aitask_sync.sh` — the guarded merge.** When `_rebase_blocked` blocks a
    DIVERGED branch, main and do_push's retry now try it before deferring:
    1. pin HEAD and @{u} to SHAs;
    2. require exactly one merge base;
    3. require disjoint `--no-renames` side sets;
    4. require a clean `merge-tree --write-tree`;
    5. check the paths the merge writes against the protected set and against
       ignored files, matching exact paths, directory/file prefixes and
       case-folded names;
    6. build the commit with `commit-tree`;
    7. advance with `merge --ff-only --no-autostash --no-overwrite-ignore`;
    8. verify the tree deterministically.

    It declines with one of nine stderr slugs (`_gm_refuse`). The wire keeps
    `DEFERRED:protected_dirty`, and `MERGED` is new.
  - **Other `aitask_sync.sh` changes:**
    - `pre_guarded_ff` test seam;
    - `_gm_note_unpublished` on every exit where the merge landed but the push
      did not;
    - `--no-renames` in `_load_incoming`;
    - header/`show_help` protocol and seam-list docs.
  - **Other surfaces:**
    - `STATUS_MERGED` in the runner, handled in both TUIs;
    - `sync.md` documents it.
  - **Tests:**
    - new `test_sync_guarded_merge.sh` (147 checks);
    - truth table — the merged cell plus overlap and incoming-rename cells;
    - deferral reshapes, completed in review;
    - t1725_4's live-pane fixture;
    - the runner parse test.
- **Deviations from plan:**
  - Test 1b asserts `MERGED` rather than switching to the overlap (it would have
    duplicated Test 1).
  - The note to t1725_4 was moot: the task landed and was archived first. This
    task reshaped its fixture instead.
  - Post-phase 1 took its "otherwise" branch, because no foreign hunks remained.
  - AC2's slug is `protected_written`. The plan had allowed either
    `protected_written` or `sides_overlap`.
  - A zero-merge-base history shares the `multiple_merge_bases` slug, with the
    count in its detail.
- **Issues encountered:**
  - **Harness false alarm.** The mutation harness's closing check counted 0
    fast-forward flags in the shared script. The file was intact: the count's
    basic regex contained `$c`, and `grep -cF` returns 1.
  - **The first review found two gaps in the reshaped fixtures,** fixed in
    Change Request 1:
    - Test 30 discarded its output;
    - Tests 33B–33D lacked the overlap assertion.
  - **The live eligibility probe was inconclusive.** The real branch was
    ahead-only.
  - **Observation, not classified as a defect:** `ait note` appended to an
    archived target and reported `NOTE_APPENDED`, with `LIVE_NONE:unlocked`.
    Whether a note to an archived task is intended could not be established
    from `aitask_note.sh`.
- **Key decisions:**
  - Merge commits on `aitask-data` are accepted routinely (user).
  - `task_data_converge` stays fast-forward-only; its hint is a recovery
    attempt, not a guarantee (user).
  - The merge is built from `merge-tree` + `commit-tree` + a guarded
    fast-forward, never `git merge` / `--abort`. That leaves no `MERGE_HEAD`,
    shared staged entries survive, and a refusal is a clean deferral.
  - A deterministic tree check replaces a racy byte-hash of the files a live
    holder owns.
  - `--no-overwrite-ignore` on the final fast-forward (user review), because a
    pre-scan cannot cover a file created after it.
  - Refusal slugs go to stderr only; the wire is unchanged.
  - Mutants run only in isolated copies (user review).
- **Upstream defects identified:**
  - `.aitask-scripts/aitask_sync.sh:1837 — do_pull_rebase runs git pull --rebase without --no-autostash, so a user's rebase.autoStash=true stashes and re-applies files the sweep deliberately left protected`
  - `.aitask-scripts/aitask_sync.sh:2165 — the existing behind-only fast-forward (merge --ff-only @{u}) runs without --no-overwrite-ignore, so it silently replaces a local ignored file (userconfig.yaml, *.local.json) that an incoming commit adds; the rebase path it falls back to likely shares this (unverified)`
  - `tests/lib/sync_fixture.sh:183 — run_sync inherits the developer's global git config (no GIT_CONFIG_GLOBAL isolation), so settings such as merge.autoStash / rebase.autoStash leak into every sync test and can mask or fake an autostash defect`
