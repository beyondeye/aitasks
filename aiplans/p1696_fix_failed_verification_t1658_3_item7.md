---
Task: t1696_fix_failed_verification_t1658_3_item7.md
Base branch: main
Output branch: main
---

# t1696 — pin that the partial-outcome `./ait sync` hint recovers with live-held files

## Context

t1658_3 item #7 failed: after a metadata update ended `UPDATED_REMOTE_ONLY` (exit 3),
the message pointed at `./ait sync`. On a box with several agents running, that
command could not recover. `ait sync` deferred on files held by live sessions
(`protected_dirty`). In the diverged shape, `task_data_converge()` and `ait sync`
each handed recovery to the other, and neither acted.

**This has since been fixed elsewhere (scope decided with the user: treat the
defect as fixed, add only the missing regression test):**

- **t1725_3** (`152254289`, `d19473e25`): the `ait sync` rebase gate now looks at
  the actual tree state. In the behind-only case (`local_ahead == 0`) it
  fast-forwards (`merge --ff-only`) instead of deferring. It still defers when an
  incoming commit touches a protected file.
- **t1731** (`e2f12c499`): when protected files block the rebase on a diverged
  branch, `ait sync` now converges it with a guarded merge (`MERGED`). The merge
  runs only if the two sides changed disjoint files and the merge is clean;
  otherwise it defers and names the guard that refused.

So every hint the task listed is now correct as written. They all name the
recovery that now works, and no wording change is needed:

- `lib/verified_update_lib.sh:241`
- `lib/task_utils.sh:1518` / `:1520` (`ff_blocked` / `local_diverged`)
- the `aitask_usage_update.sh` / `aitask_verified_update.sh` help text
- the satisfaction-feedback procedures and their goldens

The procedures and goldens stay untouched.

**Coverage check: what exists vs. what is missing.**

- `tests/test_task_push.sh` Tests 37/38 run the real `aitask_sync.sh` after
  `task_data_converge` reports `diverged` / `ff_blocked`. Their fixtures have
  **no live-locked file**, though, which is the exact condition t1696 is about.
- `tests/test_sync_guarded_merge.sh` AC1 (diverged → `MERGED`) and AC4
  (behind-only → `PULLED`) use a live-locked file. Their starting state is built
  by hand with a `pc2` clone. It is **never produced by a real metadata updater**,
  so they never check the hint.
- **Missing:** the composed scenario from item #7 and from the task's "Scope
  correction". A real `aitask_usage_update.sh` partial result, with a live-locked
  dirty task file present, then the hinted `./ait sync` executed and shown to
  converge. Two shapes need it: fast-forwardable, and diverged. The diverged shape
  includes the "absorbing state" step: a second update on a diverged branch adds
  one more commit that exists only on origin.

Automatic self-healing inside `task_data_converge()`'s diverged arm is **out of
scope**, by the user's decision.

## Implementation

### 1. New test file `tests/test_metadata_partial_sync_recovery.sh`

The fixture is `tests/lib/sync_fixture.sh`. `setup_repo` builds a branch-mode
clone with a real `.aitask-data` worktree, a full copy of `.aitask-scripts` plus
the `ait` dispatcher, and the lock branch. Reused helpers: `plant_lock`,
`lock_yaml_live`, `run_sync` and `sync_err`, plus the `dgit` / `dhead` /
`remote_sha` / `sha_of` helpers. The last four are local to
`test_sync_guarded_merge.sh` (one-liners), so redefine them locally the same way.
Header comment: what is pinned (the hint/recovery agreement, t1696) and why the
existing tests don't cover it.

Standard file skeleton, like `test_sync_guarded_merge.sh`:
- `set -uo pipefail`
- `scratch_cwd.sh` + `enter_scratch_cwd`
- `asserts.sh`, then `sync_fixture.sh`
- `PASS`/`FAIL`/`TOTAL`
- the summary footer with `[[ "$FAIL" -eq 0 ]]`

No `( … )` subshell test bodies, so no `assert_counters_init`.

Helpers in the file:
- `seed_models <T>`: write a `models_claudecode.json` with an `opus4_6` entry
  (same shape as `_mdfix_write_models` in `tests/lib/metadata_update_fixture.sh`)
  into `$T/local/.aitask-data/aitasks/metadata/`, then commit and push it on the
  data branch.
- `protect_t10 <T>`: `plant_lock "$T" 10 "$(lock_yaml_live 10)"` and append a
  line to `aitasks/t10_alpha.md`, the same as in `test_sync_guarded_merge.sh`.
- `run_usage <T>`: run `./.aitask-scripts/aitask_usage_update.sh --agent-string
  claudecode/opus4_6 --skill pick --silent` in `$T/local`. Use the fixture's PATH
  shim and `TEST_HOSTNAME`. Send stderr to `$T/usage_stderr`, and capture both
  stdout and the exit status without a pipeline.

**Cell A: fast-forwardable partial → `./ait sync` → `PULLED`** (item #7 exactly)
1. `setup_repo`, `seed_models`, `protect_t10`.
2. Force the partial result the way item #6 did. Append a byte to the local
   `models_claudecode.json`, then `run_usage`.
   - Assert stdout `UPDATED_REMOTE_ONLY:claudecode/opus4_6:pick:1` and exit `3`.
   - Assert stderr contains `./ait sync`. This is the hint under test.
3. Record `P1 = remote_sha`. Revert the probe edit with `dgit checkout --` on the
   models file. This is a fixture-owned file in a temp repo.
4. Check the preconditions:
   - `P1` is not an ancestor of HEAD.
   - The branch is behind 1 and ahead 0.
   - t10 is still dirty.
   - Record the bytes of t10.
5. `run_sync`. Assert:
   - the verdict is `PULLED`
   - `merge-base --is-ancestor P1 HEAD`
   - ahead/behind are 0/0 after a fetch
   - the t10 bytes are unchanged and still ` M`, never committed

**Cell B: diverged partial (the absorbing state) → `./ait sync` → `MERGED`**
1. Same as Cell A steps 1–3. That leaves the branch behind 1, with `P1` only on
   origin.
2. Make a local commit directly in the data worktree, touching only
   `aitasks/t20_beta.md`. The branch is now ahead 1 / behind 1, i.e. diverged.
3. Run `run_usage` again with the models file clean.
   - Assert `UPDATED_REMOTE_ONLY:…:2` and exit `3`.
   - Assert stderr names `diverged` and `./ait sync`. This reproduces "every
     subsequent pick pushes one more commit to origin only".
   - Record `P2 = remote_sha`.
   - Assert that neither P1 nor P2 is an ancestor of HEAD.
4. `run_sync`. Assert:
   - the verdict is `MERGED`
   - P1 and P2 are both ancestors of HEAD
   - the local t20 commit survived (HEAD's t20 content)
   - ahead/behind are 0/0
   - the remote equals HEAD
   - the merged `models_claudecode.json` shows `pick` runs = 2 (via `jq` on `git show`)
   - the t10 bytes are preserved, as in Cell A

**Negative control (inline, Cell B):** before step 4, run `task_data_converge`
indirectly. The second `run_usage` already did this, so the assertion that its
stderr reports `diverged` is what proves the converge seam did **not** heal it.
That shows the test reaches the state the task describes, and is not testing an
already-converged branch.

### 2. No other source edits

There are no changes to hint strings, procedures or goldens, which avoids
regenerating goldens. No `aitask_skill_verify.sh` run is needed.

## Verification

- `bash tests/test_metadata_partial_sync_recovery.sh`: all PASS, exit 0.
- **Discriminating check: two separate targeted mutations, one per recovery
  path.** One mutation cannot cover both cells. In `main`
  (`aitask_sync.sh:2223`), a blocked `_rebase_blocked` falls through to
  `_converge_by_guarded_merge`. So forcing "blocked" only defeats Cell A's
  fast-forward; Cell B's disjoint diverged state still ends `MERGED`.

  Run the mutations against a **scratch copy** of the project: `ait`,
  `.aitask-scripts/` and `tests/` copied under the session scratchpad. The test
  derives `PROJECT_DIR` from its own location, so the fixture copies the mutated
  scripts. No committed file is touched. For each mutation, `grep` the scratch
  `aitask_sync.sh` first to prove it applied, then run the scratch copy of the
  new test:
  - **M1, the fast-forward path (Cell A).** Insert `return 0` as the first
    statement of `_rebase_blocked`, i.e. always blocked.
    - Expected: Cell A's recovery assertions go red. The verdict is
      `DEFERRED:protected_dirty`, because the guarded merge declines a branch
      that is not diverged; P1 is not an ancestor and the branch is still
      behind 1.
    - Cell B stays green, which confirms that M1 alone cannot detect a Cell B
      regression.
  - **M2, the guarded-merge path (Cell B).** Insert `return 1` as the first
    statement of `_converge_by_guarded_merge`, i.e. declined with nothing
    changed.
    - Expected: Cell B's recovery assertions go red. The verdict is
      `DEFERRED:protected_dirty`; P1/P2 are not ancestors and the branch is
      still diverged.
    - Cell A stays green, because it never reaches the guarded merge.
    - This is safe under `set -u`: the `GM_*` globals are initialized at script
      scope (`aitask_sync.sh:1581-1589`), so the refusal line prints
      `(unknown)` rather than crashing. Under M1, the proof that Cell A declines
      is `_guarded_merge_prepare`'s `not_diverged` refusal
      (`aitask_sync.sh:1655-1658`).
  - **Restoration.** Re-copy the unmutated `aitask_sync.sh` into the scratch
    tree and re-run: both cells are green again. Then run the real-tree test
    (above), which is green.
  - Record each mutation's red/green cell counts in the Final Implementation
    Notes.
- `shellcheck tests/test_metadata_partial_sync_recovery.sh`.
- Re-run the neighbouring suites: `bash tests/test_sync_guarded_merge.sh` and
  `bash tests/test_usage_update.sh`. Neither is changed; this is a sanity check
  of the fixture.

## Risk

### Code-health risk: low
None identified. The change adds one new test file and edits no source,
procedure or golden. It reuses the existing `sync_fixture.sh`. The live-lock
anchor (`$$`) and the no-server tmux socket are the same patterns
`test_sync_guarded_merge.sh` already uses.

### Goal-achievement risk: low
- Feasibility: `aitask_usage_update.sh` has not been run inside `sync_fixture`'s
  repo before. It needs `jq`, the models file committed on the data branch, and
  an origin URL its remote clone can reach. All of these exist there: there is
  a full copy of `.aitask-scripts` and a local bare remote. If something is
  missing, the fix is a fixture-local seed in this test file, not a change to
  the approach. · severity: low · → mitigation: none (handled in the step)

## Post-Review Changes

### Change Request 1 (2026-10-12 16:30)
- **Requested by user:** `OUT="$(run_sync "$T")"` dropped the recovery's exit
  status, so a recovery that converged but exited non-zero still passed. The
  reviewer confirmed this: making both recovery calls exit 7 still gave 36/36.
- **Changes made:** both cells capture `$?` directly from the command
  substitution, with no pipeline, and assert `the hinted recovery exits 0`.
  Re-checked with the same mutation (M3: `; exit 7` after the sync call in a
  scratch `sync_fixture.sh`): exactly those two assertions fail, and the suite
  exits 1.
- **Files affected:** `tests/test_metadata_partial_sync_recovery.sh`

## Final Implementation Notes
- **Actual work done:** added one file,
  `tests/test_metadata_partial_sync_recovery.sh`, with 38 assertions in two
  cells.
  - Each cell starts with a real `aitask_usage_update.sh` partial result
    (`UPDATED_REMOTE_ONLY`, exit 3) while a live-locked dirty `t10` is present.
    It checks that stderr names `./ait sync`, then runs that recovery.
  - **Cell A** (behind-only) → `PULLED`.
  - **Cell B** (diverged, plus a second partial update that the converge seam
    reports as `[diverged]`) → `MERGED`.
  - Both cells assert a 0 exit status, the metadata commits are now ancestors of
    HEAD, the branch is 0 ahead / 0 behind, and `t10` keeps its bytes, stays
    ` M` and is in no commit. Cell B also asserts the registry merged to 2 runs,
    the local t20 commit survived, and the remote equals HEAD.
- **The original t1658_3 item #7 defect was fixed elsewhere:**
  - t1725_3 (`152254289`, `d19473e25`): fast-forward when behind-only.
  - t1731 (`e2f12c499`): guarded merge when diverged.
  - So the `./ait sync` hints in `verified_update_lib.sh`, `task_utils.sh`
    (`ff_blocked` / `local_diverged`), the updater help text and the
    satisfaction-feedback procedures are correct as written. No hint, procedure
    or golden was changed.
  - Self-healing inside `task_data_converge()`'s diverged arm is deliberately
    out of scope (user decision). That arm still hands off to `./ait sync`, and
    nothing runs `./ait sync` automatically.
- **Deviations from plan:**
  - The SC2031 shellcheck info (a false positive caused by the fixture's
    `run_sync` exporting in its own subshell) is silenced with a commented
    disable, like `tests/test_tmux_control.sh:156`.
  - `run_usage` passes the environment inline instead of using `export`.
  - The footer matches `test_sync_guarded_merge.sh`.
- **Issues encountered:** none. The updater ran unchanged inside
  `sync_fixture`'s repo: there is a full copy of `.aitask-scripts`, a local bare
  remote and `jq`.
- **Key decisions:** discriminating checks used separate targeted mutations,
  each in a scratch project copy:
  - **M1** (`_rebase_blocked` always returns blocked): 3 Cell A recovery
    assertions red, each `DEFERRED:protected_dirty`; Cell B green.
  - **M2** (`_converge_by_guarded_merge` returns 1): 7 Cell B recovery
    assertions red; Cell A green.
  - **M3** (recovery exits 7): only the two exit assertions red.
  - The restored copies are byte-identical to the real files, and the real tree
    passes 38/38.
  - Neighbouring suites unchanged: `test_sync_guarded_merge.sh` 147/147,
    `test_usage_update.sh` 88/88.
- **Upstream defects identified:** None

## Step 9

Standard post-implementation (current branch, no worktree). Commit the test as
`test: Pin that the partial-outcome './ait sync' hint recovers with live-held files (t1696)`,
then archive.
