---
Task: t1928_coordinate_opencode_refresh_with_counter_writers.md
Base branch: main
Output branch: main
---

# t1928 — Coordinate writers of models_opencode.json with a shared compare-and-swap

## Context

Three writers do a read-modify-write of `aitasks/metadata/models_*.json` with
no coordination between them:

- `aitask_opencode_models.sh` (the refresh) reads the registry in
  `merge_with_existing` with `cat`, merges in the discovered models, then
  writes with `jq … > "$METADATA_FILE"`.
- `aitask_usage_update.sh::update_model_file` and
  `aitask_verified_update.sh::update_model_file` render the registry with
  `jq … "$models_file" > $TMPDIR/tmp`, then `mv` the temp over the registry
  (`:248` / `:276`). On the no-remote path that file is the live registry.
  On the remote path it is a temp clone, which is later applied locally by an
  ff-only converge.

Two orderings each lose data without any error:

1. **Forward (the defect named in the task):** a counter write lands between the
   refresh's read and its write, and the refresh overwrites it.
2. **Reverse:** a no-remote counter writer reads the old registry, the refresh
   swaps its result in, and then the writer's `mv` replaces that result with
   its own stale copy (rows and notes from the refresh are lost). A CAS added
   only to the refresh can't see this.

Not part of either window: once the refresh has written, the remote path's
converge (`task_data_converge`, `merge --ff-only`) **refuses the dirty file**
(`ff_blocked`). That case shows up as `UPDATED_REMOTE_ONLY` or a push conflict,
not as silent loss.

**Approach (user-chosen): symmetric optimistic CAS in a new shared lib,
`lib/registry_cas.sh`, used by all three writers.** Each writer works like this:

1. Take a byte snapshot of the registry. A missing file is also a state.
2. Render the new content **from the snapshot**.
3. Stage it in a temp file beside the registry (`ait_atomic_render`).
4. As the last step before the rename, confirm the live file still matches the
   snapshot. If it does, rename. If it doesn't, re-snapshot and re-render, with
   a bounded number of attempts.
5. If the file never stops changing, fail closed: write nothing and return a
   distinct status.

Each writer then notices a swap made by any of the others in either order. It
also notices a swap made by a generic pull, which a lock would not cover.

What's left open is each writer's own few milliseconds between its final
compare and its rename, which the user has accepted. A side benefit: the
counters' `mv` from `$TMPDIR` (which turns into a non-atomic copy across
filesystems) becomes a same-directory atomic rename.

Current-branch mode (profile `fast`): no worktree.

## Implementation steps

### 1. New `.aitask-scripts/lib/registry_cas.sh`

- Guard against double-sourcing (`_AIT_REGISTRY_CAS_LOADED`), and source
  `atomic_write.sh` from its own directory, the same way `registry_lock.sh`
  sources `stale_lock.sh`.
- Header: describe the contract and why it's optimistic and not a lock
  (generic pulls never take a lock; the CAS catches every writer). State the
  remaining compare→rename gap. Add the rule that **render functions must
  `return`, never `exit`/`die`**, so the snapshot temp dir is always cleaned up.
  Don't set an EXIT trap; the reason is the same one `atomic_write.sh` gives,
  and the counter writers already have one of their own. Keep the header free
  of the literal `aitasks/metadata` / `metadata_file` spellings so the writer
  inventory doesn't read this generic lib as a metadata writer. Run the
  inventory test to confirm.
- API:
  `ait_cas_rewrite <dest> <max_attempts> <render_fn> [args...]`. It calls
  `render_fn <snapshot_path_or_empty> [args...]`, which prints the new content.
  - Return `0` when swapped, `1` when the render or staging failed (dest left
    untouched), and `2` when dest changed on every attempt (nothing written).
  - Set the global `AIT_CAS_ATTEMPTS` to the number of attempts used, so callers
    can report a retry. The lib itself prints nothing, so it never pollutes a
    caller's `--silent` stdout or a `$( )`-captured value.
  - Internals:
    - `mktemp -d` for the snapshot, removed on every return path.
    - `_ait_cas_snapshot`: `cp` the file, or record "absent".
    - `_ait_cas_unchanged`: when absent, the file must still be absent;
      otherwise `cmp -s`.
    - `_ait_cas_render` is the renderer passed to `ait_atomic_render`. It runs
      `render_fn` (`|| return 1`), then the test hook (`|| return 1`), then the
      compare as its **last** act, setting `_AIT_CAS_CHANGED=1` and returning 1
      on a mismatch. `ait_atomic_render` runs it in the current shell, so the
      flag carries back.
  - Test seam, modelled on `AITASK_VERIFIED_UPDATE_BEFORE_PUSH_HOOK`: if
    `AIT_CAS_BEFORE_SWAP_HOOK` is set, run
    `AIT_CAS_ATTEMPT=<n> AIT_CAS_DEST=<dest> bash "$hook" >&2`. It runs after the
    render and before the compare, and its stdout goes to stderr so it can never
    end up in the staged file.
- Add a one-line pointer in the `atomic_write.sh` header ("a caller that
  read-modify-writes a shared file must hold its own mutex") to
  `registry_cas.sh` as the optimistic alternative.

### 2. `.aitask-scripts/aitask_opencode_models.sh`

- Source `lib/registry_cas.sh`.
- Turn the reserved-name block into `reserved_guard_message <registry_file>`.
  It builds the same message text (unchanged wording) from the discovered set
  plus the given file's rows, and prints nothing when the file is clean. The
  existing pre-write guard calls it on `$METADATA_FILE` and `die`s, which keeps
  today's behavior and the expectations in `test_opencode_models_reserved.sh`.
- The dry-run block is unchanged and read-only: it merges against the live file.
- Write path:
  ```bash
  render_refresh() {   # <snapshot> ; render fn for ait_cas_rewrite — return, never die
      RESERVED_MSG="$(reserved_guard_message "$1")" || return 1
      [[ -z "$RESERVED_MSG" ]] || return 1
      merged="$(merge_with_existing "$discovered" "$1")" || return 1
      jq --indent 2 '.models |= sort_by(.name)' <<< "$merged" || return 1
  }
  ```
  Call it as `ait_cas_rewrite "$METADATA_FILE" "$MAX_SWAP_ATTEMPTS" render_refresh || cas_rc=$?`
  with `MAX_SWAP_ATTEMPTS=5`.
  - If `RESERVED_MSG` is set, `die` with it. A reserved row that arrived in the
    middle of the run fails closed the same way.
  - On rc 2, `die "$METADATA_FILE kept changing during the refresh (5 attempts) — a concurrent writer is active. Nothing was written; re-run."`.
  - On any other non-zero rc, `die "Failed to write $METADATA_FILE"`.
  - When `AIT_CAS_ATTEMPTS > 1`, print
    `info "… changed while merging; re-merged on the fresh content (N attempts)"`.
- `merge_with_existing` keeps its name and signature, so the inventory pin
  stays valid. It now receives the snapshot path, or `""` when the file is
  absent; its `[[ ! -f ]]` branch already handles that. Counts and the success
  line come from the final `$merged`. `--sync-seed` runs only after a
  successful swap.
- Update the header comment that describes the merge.

### 3. Counter writers: `aitask_usage_update.sh` and `aitask_verified_update.sh`

- Source `lib/registry_cas.sh` at startup.
- Split `update_model_file`. The render function is
  `render_usage_bump <snapshot> <model> <skill>` or
  `render_verified_update <snapshot> <model> <skill> <score>`. Because it can
  run against several fresh snapshots, it **re-validates the target on each
  one** and **produces the value from what it rendered**:
  ```bash
  render_usage_bump() {   # return, never die — see registry_cas.sh
      RENDER_MODEL_GONE=0; RENDERED_VALUE=""
      if ! jq -e --arg model "$2" 'any(.models[]; .name == $model)' "$1" >/dev/null 2>&1; then
          RENDER_MODEL_GONE=1; return 1     # renamed/removed by a concurrent refresh
      fi
      local out
      out="$(jq … "$1")" || return 1          # the existing jq program, unchanged
      RENDERED_VALUE="$(jq -r --arg model "$2" --arg skill "$3" '<existing value query>' <<< "$out")" || return 1
      [[ -n "$RENDERED_VALUE" && "$RENDERED_VALUE" != null ]] || return 1
      printf '%s\n' "$out"   # jq's single trailing newline, byte-identical to before
  }
  ```
  - `update_model_file` calls `ait_cas_rewrite "$models_file" 5 <render_fn> …`
    and checks the outcome explicitly. It can't rely on errexit, because the
    remote wrapper calls it under `set +e`:
    - rc 0 → `printf '%s\n' "$RENDERED_VALUE"`. The value comes from the
      swapped content, not from a later re-read of the live file, which closes
      the race where a rename slips in after the swap.
    - `RENDER_MODEL_GONE=1` →
      `die "Model '<m>' is no longer in $models_file (renamed or removed by a concurrent refresh) — nothing was recorded; re-run"`.
    - rc 2 → `die "$models_file kept changing while recording … — nothing was recorded; re-run"`.
    - Any other rc → `die "Failed to update $models_file — nothing was recorded"`.
    - When `AIT_CAS_ATTEMPTS > 1` and the run isn't `--silent`, send a `warn`
      to stderr. Stdout carries only the value.
  - `mktemp` / `mv` and the post-swap live `jq -r` read are removed from both
    scripts. The `_AIT_UPDATE_MODEL_FILE_FN` contract stays as it is (args in,
    value on stdout, non-zero on failure).
  - `ensure_model_exists` stays as the early, user-facing check. The
    per-snapshot check is what keeps the guarantee during retries.
- This applies on both paths. Inside the remote temp clone nothing else writes,
  so the CAS swaps on the first attempt.

### 3b. `.aitask-scripts/lib/verified_update_lib.sh`: propagate a callback failure on the remote path

`commit_metadata_update` calls `commit_and_push_from_remote_clone` under
`set +e`. That function's `new_value="$("$_AIT_UPDATE_MODEL_FILE_FN" …)"`
(`:193`) doesn't check the callback's status, so a failing callback leaves the
clone unchanged. It then reaches the diff-quiet branch and returns 0 with an
empty `AIT_METADATA_VALUE` and `AIT_METADATA_LOCAL_CONVERGED=1`, and the caller
prints `UPDATED:`. This defect predates the change, but the new failure modes
(CAS rc 1/2, model gone) make it reachable. Fix:
```bash
if ! new_value="$("$_AIT_UPDATE_MODEL_FILE_FN" "$clone_dir/$models_file" "$model_name" "$skill_name" "$extra_arg")" \
        || [[ -z "$new_value" ]]; then
    rm -rf "$tmpdir"
    die "Failed to update $models_file in the task data clone — nothing was committed or pushed"
fi
```
This runs before `git add`, before the commit and before any no-change
verdict. `die` exits the script, so `main()` never reaches its `UPDATED:` /
`UPDATED_REMOTE_ONLY:` echo, and the `set +e` around the call doesn't hide it.
Add a comment explaining why the status is checked explicitly here.

### 4. Test scaffolding (the source-on-startup ↔ scaffold rule)

- In `tests/lib/test_scaffold.sh::setup_fake_aitask_repo()`, copy
  `lib/registry_cas.sh` next to `atomic_write.sh`, with the same kind of comment.
- Wherever a fixture copies `verified_update_lib.sh` or the opencode script by
  hand without the scaffold, also copy `registry_cas.sh` and `atomic_write.sh`.
  Those fixtures are in `tests/lib/metadata_update_fixture.sh` (2 sites),
  `tests/test_usage_update.sh`, `tests/test_verified_update.sh`,
  `tests/test_opencode_models_merge.sh` and `tests/test_opencode_models_reserved.sh`.
  Check each one; skip a site where the scaffold already provides the libs.

### 5. Tests

- **New `tests/test_registry_cas.sh`** (unit tests of the lib, run under a
  private `TMPDIR` so leaked temps can be detected):
  - (a) Unchanged registry: swapped, `AIT_CAS_ATTEMPTS=1`, and no `.<dest>.*`
    temp left beside it.
  - (b) The hook rewrites dest on attempt 1. Given `{"n":0}`, a render of
    `.n += 1` and a hook that sets `n=100`, the final `n` is `101` and there
    were 2 attempts.
  - (c) The hook changes dest on every attempt: rc 2, dest holds the hook's last
    write, and neither temps nor the snapshot dir are left behind.
  - (d) The render fails: rc 1, dest byte-identical to before.
  - (e) Absent dest: it gets created. Absent dest that the hook creates on
    attempt 1: the retry renders from the created file.
- **`tests/test_opencode_models_merge.sh`**, new cases that use
  `AIT_CAS_BEFORE_SWAP_HOOK`:
  - Test 6 (forward): on attempt 1 the hook sets `usagestats…runs=7`. Expect
    exit 0, runs 7 in both the registry and the seed, regenerated notes, and
    `re-merged` in the log.
  - Test 7: the hook changes the registry on every attempt. Expect a non-zero
    exit, `Nothing was written`, old notes, and no seed file.
  - Test 8: the registry is absent and the hook creates it on attempt 1. The
    row keeps the hook's `usagestats` and gets regenerated notes.
- **Stale local writer (reverse ordering), deterministic.** Add one case each
  to `tests/test_usage_update.sh` and `tests/test_verified_update.sh`, using
  their no-remote fixture. The hook (attempt 1 only) simulates a refresh
  swapping in mid-update: it rewrites the target row's `notes` and adds a new
  row. Expect the writer to exit 0 with `UPDATED:`, and the final registry to
  keep **both** the refresh's notes and row **and** the bumped count/score.
  The writer read the old registry first, which is exactly the ordering the
  review raised.
- **Target renamed between attempts.** Add one case each to the usage and
  verified tests, using the no-remote fixture. On attempt 1 the hook does what
  the refresh does through cli_id matching: it renames the target row to a new
  name with the same `cli_id`. Expect a non-zero exit, stderr containing
  `no longer in`, **no** `UPDATED:` or `UPDATED_REMOTE_ONLY:` in the output, and
  a registry equal to the hook's version, with no stats added under either name.
- **Remote-path callback failure.** Add one case each to the usage and verified
  tests, using their remote fixture (origin + data branch). A hook that exits 1
  makes the in-clone CAS fail, and the callback fails with it. Expect a non-zero
  exit, neither `UPDATED:` nor `UPDATED_REMOTE_ONLY:` in the output, the origin
  branch tip unchanged (no commit pushed), and the local registry unchanged.
- Update the header comments of the touched test files to name the seam.
- `tests/test_metadata_writer_inventory.py` is **not** edited. The pinned sites
  `merge_with_existing` and the two `update_model_file` functions still exist,
  and the file carries another session's uncommitted edit, which this commit
  must not pick up. Running it confirms nothing needs re-pinning.

## Verification

- `bash tests/test_registry_cas.sh`, `bash tests/test_opencode_models_merge.sh`,
  `bash tests/test_opencode_models_reserved.sh`, `bash tests/test_usage_update.sh`,
  `bash tests/test_verified_update.sh`, `bash tests/test_verified_update_flags.sh`:
  all pass.
- `python3 tests/test_metadata_writer_inventory.py` passes.
- **Negative control (mutant, per review).** Make the compare **always succeed**,
  so changes are never detected: `_ait_cas_unchanged() { return 0; }`. Do this
  on a backup-then-edit of my own new, untracked `registry_cas.sh` (no git
  restore), then restore it from the backup and `cmp` to confirm. Under the
  mutant these must FAIL:
  - registry_cas (b): `n` is 1 because the hook's 100 is lost.
  - registry_cas (c): rc is 0 because it wrote anyway.
  - opencode Test 6: the count is lost.
  - opencode Test 7: exit 0 with regenerated notes.
  - Both stale-local-writer cases: the refresh's notes and row are lost.

  Each failure has to come from the lost-update or unwanted-write assertion.
  None may come from a refused write. The unmutated suites must pass again
  after the restore.
- **Two more mutants, each in a scratch copy of the script or lib, restored
  and `cmp`-checked the same way.** These files are tracked but have no other
  uncommitted edits, so I back them up myself and never use git restore:
  - Drop the per-snapshot model check from the usage renderer. The
    renamed-target case must fail, because the writer reports `UPDATED:` with
    nothing recorded.
  - Drop the status check from 3b (bare `new_value="$(…)"`). The remote
    callback-failure case must fail, because `UPDATED:` gets printed.
- `shellcheck` on the new lib, the three writer scripts and the touched tests.
- Step 9 (Post-Implementation): current-branch mode means no merge, then
  verification/gates and archival.

## Risk

### Code-health risk: medium
- Touches the hot path of both counter writers. Usage bumps run on every
  workflow completion. That path now creates a snapshot temp dir and can fail
  with a new rc-2 die where it used to always write. This is covered by the
  existing usage/verified suites plus the new cases, and the jq programs move
  unchanged. · severity: medium · → mitigation: none
- `verified_update_lib.sh`'s remote wrapper changes in one place (an explicit
  status check before any git mutation). It's a shared seam used by both
  counter writers. It is covered by the existing remote suites plus the new
  callback-failure regression, and the mutant confirms the regression isn't
  passing vacuously. · severity: low · → mitigation: none
- New lib dependency for every scaffolded test: a missed fixture copy fails
  closed inside those tests. This is mitigated by step 4's audit of every
  fixture and by running the suites that are affected. · severity: low · → mitigation: none

### Goal-achievement risk: low
- A few milliseconds remain on each writer between its final compare and its
  rename (accepted by the user). · severity: low · → mitigation: none
- Out of scope: the period between the refresh writing and the refresh skill's
  Step 8 commit. That case isn't silent: ff-only converge refuses the dirty
  file, which surfaces as `UPDATED_REMOTE_ONLY` or a push conflict. · severity: low · → mitigation: none

`risk_mitigations_planned = false`. The coordination choice was just settled
with the user, and the regression and mutant coverage above is part of the
plan itself.

## Final Implementation Notes
- **Actual work done:** New `.aitask-scripts/lib/registry_cas.sh` (`ait_cas_rewrite`: snapshot → render from snapshot → stage beside dest via `ait_atomic_render` → compare as the renderer's last act → rename, retry on change, rc 0/1/2, `AIT_CAS_ATTEMPTS` out-param, `AIT_CAS_BEFORE_SWAP_HOOK` test seam). The refresh (`aitask_opencode_models.sh`) writes through it with a per-attempt `render_refresh` (re-merge + reserved-name re-check from the snapshot); the reserved guard became `reserved_guard_message`. Both counter writers' `update_model_file` now go through `render_usage_bump` / `render_verified_update`, which re-check the target per snapshot (`RENDER_MODEL_GONE`) and derive the value from the rendered content (`RENDERED_VALUE`). `verified_update_lib.sh` gained `REGISTRY_CAS_ATTEMPTS=5` and an explicit callback-status check in `commit_and_push_from_remote_clone`. `atomic_write.sh` header points at the new lib.
- **Deviations from plan:** None in substance. `REGISTRY_CAS_ATTEMPTS` lives in `verified_update_lib.sh` (the counters' shared lib) rather than per script. Only the two opencode tests needed explicit lib copies — every counter fixture goes through `setup_fake_aitask_repo`, so one scaffold line covered them. The concurrent-writer hook builders (`mdfix_write_refresh_hook`, `mdfix_write_rename_hook`) went into `tests/lib/metadata_update_fixture.sh`, shared by both counter suites.
- **Issues encountered:** `tests/test_verified_update_flags.sh` runs against the REAL repo and pushes `test_414_flags` verified-score commits to `origin/aitask-data` (pre-existing; the key already had 85 runs). Running it here pushed 2 more and exited 3 (`UPDATED_REMOTE_ONLY`) because the local data branch was diverged from origin — environmental, unrelated to this change. Not re-run.
- **Key decisions:** Optimistic CAS over a lock (user choice), because generic pulls also mutate the registry and would never take a lock; the residual few-ms compare→rename gap per writer is accepted and documented in the lib. Render functions must `return`, never `exit`, so the snapshot temp dir is always cleaned inline (no EXIT trap — the counters own theirs). Negative controls ran in a scratch copy of `.aitask-scripts/` + `tests/`, never mutating live files: compare-always-true fails the lost-update/unwanted-write assertions in all four suites; removing the per-snapshot model check fails the renamed-target case (false `UPDATED:`); removing the remote status check fails the remote callback-failure case (false `UPDATED:`).
- **Upstream defects identified:**
  - `tests/test_verified_update_flags.sh:27-33 — runs aitask_verified_update.sh in PROJECT_DIR against the real registry, so every run commits and pushes junk test_414_flags verified scores to origin/aitask-data (87 runs recorded so far); it should use a scaffolded fixture repo`
