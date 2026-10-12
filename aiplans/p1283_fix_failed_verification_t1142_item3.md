---
Task: t1283_fix_failed_verification_t1142_item3.md
Base branch: main
Output branch: main
---

# t1283 — dir artifact backend: fail closed on a bad store root

## Context

Manual verification t1142 item #3 found two defects in
`.aitask-scripts/lib/artifact_backends/dir.sh` (unchanged since 640fc94f4):

- **D1 — swallowed `die`, store degenerates to `/`.** `_artifact_dir_root` dies
  inside the `$( )` of `_artifact_dir_blob_path`, so only the subshell exits.
  The outer `printf '%s/%s'` yields `/<2hex>/<62hex>` and `put` goes on to
  `mkdir`/`mktemp` at the filesystem root (stopped only by `/` being
  unwritable). `head` likewise reports "absent" instead of dying. The
  user-visible error (`mktemp failed in /34`) hides the real cause.
- **D2 — any existing directory is accepted as the store.** The only root check
  is `[[ -d $ARTIFACT_DIR_ROOT ]]`, so a wrong-but-existing path, or an empty
  persistent mountpoint of an unmounted share (t1284 clause 2), silently
  receives blobs; the manifest is committed claiming `backend: dir` and other
  checkouts get "blob not found".

Outcome: every dir op validates the root **in the current shell** (so `die`
really exits, even under `with_attach_lock`'s errexit-suppressed tree), never
derives a path from an empty root, and refuses a root that does not carry a
store **marker file**. The marker is written only by an explicit, human-run
`ait artifact init-store dir` — never at first use, because "first use" of an
empty unmounted mountpoint is exactly the trap.

Why validate in the ops, not in `artifact_registry_activate`: `ait artifact get`
activates the backend and then serves a warm cache offline (asserted in
`tests/test_artifact_dir_backend.sh` §C/§D). Activation-time validation would
break offline reads; op-time validation only fires when the store is actually
touched.

## Implementation

### 1. `.aitask-scripts/lib/artifact_backends/dir.sh`

- Add `_ARTIFACT_DIR_MARKER=".ait-artifact-store"` (header comment: what it is,
  who writes it, why first-use creation is refused).
- Replace `_artifact_dir_root` with two helpers, both documented as **never to
  be called inside `$( )`** (they set a global / exit the current shell):
  - `_artifact_dir_check_root` — **non-fatal predicate**: returns 0 when the
    root is usable, else sets `_ARTIFACT_DIR_ROOT_ERROR` and returns 1. Checks,
    in order:
    1. `ARTIFACT_DIR_ROOT` set (existing message);
    2. `-d` root → `backend root not found: <root> (is the share mounted?)`
       (existing wording kept — tests and t1284 grep it);
    3. `-f <root>/$_ARTIFACT_DIR_MARKER` →
       `artifact_dir: <root> is not an initialized artifact store (no .ait-artifact-store marker) — is the share mounted there? If this directory IS the share, run: ait artifact init-store dir`.
  - `_artifact_dir_require_root` — `_artifact_dir_check_root || die "$_ARTIFACT_DIR_ROOT_ERROR"`.
- `_artifact_dir_blob_path`: read `$ARTIFACT_DIR_ROOT` directly; `return 1` when
  it is empty (defense in depth — never produce `/<2>/<62>`).
- **Forward ops die; delete returns.** `head`, `put`, `get`, `list` call
  `_artifact_dir_require_root` as their first statement (fail closed — `die`
  exits the current shell even under `with_attach_lock`), and capture the blob
  path with `|| die "...: could not derive blob path"`.
  `artifact_dir_delete` **never dies**: `_artifact_dir_check_root || { warn
  "artifact_dir_delete: $_ARTIFACT_DIR_ROOT_ERROR"; return 1; }`, path capture
  `|| return 1`, `rm -f ... || return 1`. Reason (comment it at the function):
  delete is the op rollback hooks (`_artifact_rollback_create_blobs`,
  `_artifact_rollback_move_blobs`, `_attach_rollback_add_blobs`) call from the
  chained EXIT trap; an `exit` there would skip the rest of `_txn_exit_trap`
  (rollback report, snapshot cleanup) and the chained `registry_lock_release`,
  leaking the global attach lock. Every caller already handles a returned
  failure (`|| txn_rollback_failed` in the hooks, `|| die` in rm/gc), matching
  the "thin front that returns status" contract in `lib/attachment_lock.sh`.
  This also fixes a silent lie in the current code: with the root missing, the
  old `rm -f "/<2>/<62>"` returned 0, so a rollback recorded the blob as deleted.
- **State the validation boundary** in the file header: the root is validated
  once at op entry; `put` then works on absolute paths, so a share unmounted
  *between* validation and the shard `mkdir`/`mv` is not protected against
  (follow-up task, see below).
- New `artifact_dir_init`: requires `ARTIFACT_DIR_ROOT` set and an existing
  directory (die with the "is the share mounted?" message; **never** `mkdir` the
  root). Marker present → print `ALREADY_INITIALIZED:<root>`, return 0.
  Otherwise write the marker atomically (`mktemp` in the root + `mv`, each
  `|| die`), content a one-line format tag (`aitasks artifact store v1`), print
  `INITIALIZED:<root>`.
- Update the file header comment (the "must ALREADY EXIST" paragraph now also
  covers the empty-mountpoint case via the marker).

### 2. `.aitask-scripts/lib/artifact_backend.sh`

- Add `artifact_backend_init` to the contract comment and as a dispatched op
  (`artifact_backend_init() { _artifact_backend_call init "$@"; }`).
- `.aitask-scripts/lib/artifact_backends/local.sh`: add `artifact_local_init`
  printing `NOTHING_TO_INIT:local` (local needs no initialization) — keeps the
  dispatcher uniform; future adapters add their own at the extension point.

### 3. `.aitask-scripts/aitask_artifact.sh`

- New verb `init-store <backend>`: `artifact_registry_activate "$backend"` then
  `artifact_backend_init`, mapping the lines above to `success`/`info` output.
  No attach lock (touches no git state; the marker write is idempotent and
  atomic). Add to `main()` dispatch and `show_help` (one line, plus a short note
  that a `dir` store must be initialized once, with the share mounted).
- Update the header STATE comment to mention the marker.

### 4. Docs

- `seed/project_config.yaml` `dir` comment: add "initialize the store once with
  `ait artifact init-store dir` while the share is mounted; every operation
  refuses a root without the marker (catches an unmounted share or a wrong
  path)".
- `aidocs/unified_artifact_design.md` §6: one sentence on the marker /
  `init-store` requirement, current-state wording.

### 5. Tests

Fixtures that use a dir store must initialize it (positive control of
`init-store`):
- `tests/test_artifact_dir_backend.sh` — after `mkdir $STORE`, run
  `artifact_registry_activate dir; artifact_backend_init` before §A.
- `tests/test_artifact_share_resolution.sh` — `"$ART" init-store dir` after the
  first `write_config` (the `cp -r $STORE store2` copy carries the marker).
- `tests/test_artifact_cli.sh` §J — `"$ART" init-store dir` after registering.

New cases in `tests/test_artifact_dir_backend.sh` (lib level):
- **D1 red/green:** with `ARTIFACT_DIR_ROOT` pointing at a missing path, run
  `( artifact_backend_head "$H" || true; echo CONTINUED )` — assert nonzero exit,
  "is the share mounted" in output, and **no `CONTINUED`** (pre-fix, head
  returned "absent" and execution continued). Same shape for `put`, also
  asserting the output contains no `mktemp`/`mkdir` (no root-derived path).
- `_artifact_dir_blob_path` with empty root returns nonzero and prints nothing.
- **D2:** an existing empty dir without marker → `put` dies with "not an
  initialized artifact store", the dir stays empty (`find` → nothing).
- `init`: missing root dies and is **not** created; existing root gets the
  marker; second run prints `ALREADY_INITIALIZED`; `init` on `local` prints
  `NOTHING_TO_INIT`.

New e2e cases in `tests/test_artifact_share_resolution.sh` (real CLI, so the
`with_attach_lock` suppression is exercised):
- config → non-existent path: `create --backend dir` exits nonzero, output names
  "is the share mounted", contains no `mktemp failed`; no new commit, no
  manifest file, task file unchanged.
- config → existing unmarked empty dir (the t1142 #3b / t1284 persistent
  mountpoint case): `create` exits nonzero with the not-initialized message, the
  dir stays empty, no commit/manifest.
- `init-store dir` on a missing path dies and does not create it.
- restore config; cold-cache `get` of an existing handle with the marker
  removed dies actionably (read path also refuses).
- **Rollback fault injection (store vanishes mid-transaction).** Reuses the
  existing failing-pre-commit-hook technique (§ "Commit-failure rollback"):
  the hook `mv`s `$STORE` away and `exit 1`s, so `create --backend dir` has
  already put the blob when the commit fails and the rollback hook must delete
  it from an unusable store. Run with `ATTACH_LOCK_TIMEOUT=2`. Assert:
  - nonzero exit; output contains the incomplete-rollback report naming the
    blob ("could not be deleted") — the unavailable-store deletion is
    **recorded**, not claimed done;
  - remaining cleanup completed: manifest absent, `git status --porcelain --
    aitasks/ artifacts/ attachments/` empty, no `.put.*` residue;
  - **attach lock released**: the lock dir (`attachments/.attach.lock`) does not
    exist, and after restoring `$STORE` an immediate `create` succeeds (no
    "another attach operation is in progress").
  Red proof: with `artifact_dir_delete` dying (the first version of this plan)
  the lock-released assertions fail.
- Negative control for the delete contract (lib level): `artifact_backend_delete`
  on an unusable root returns 1, prints the cause, and execution continues
  (`( artifact_backend_delete "$H"; echo CONTINUED )` → `CONTINUED` present,
  rc of delete 1).

## Verification

```bash
bash tests/test_artifact_dir_backend.sh
bash tests/test_artifact_share_resolution.sh
bash tests/test_artifact_cli.sh
bash tests/test_attach_local_backend.sh
bash tests/test_attach_lock_callback_contract.sh
shellcheck .aitask-scripts/aitask_artifact.sh .aitask-scripts/lib/artifact_backend.sh \
  .aitask-scripts/lib/artifact_backends/dir.sh .aitask-scripts/lib/artifact_backends/local.sh
```

Red proof: run the new D1/D2 cases against the pre-fix `dir.sh` (copy of the
HEAD version in a scratch dir, sourced in place of the fixed one) and confirm
they fail, then pass with the fix.

After implementation (Step 8d, from `### Planned mitigations` — disposition
decided by the user in chat): create the follow-up task — **dir backend:
protect `put` against a share unmounted between root validation and the blob
write**. Scope: keep every filesystem operation of `put` (shard `mkdir`, temp
file, final `mv`) tied to the validated directory itself, e.g. by holding it as
an fd / cwd and using relative paths, so nothing is re-resolved by pathname.
Acceptance: a test that makes the share disappear between validation and
mutation and shows that **no shard, temp file or final blob** lands in the
underlying mountpoint. Pathname re-checks are explicitly out, marker or
device/inode alike: they race the same way, and a check placed before `mv`
comes after `mkdir`/`mktemp` have already written there.

After commit: send t1284 a note — its unmount scenario (clause 1 and the
persistent-mountpoint clause 2) is now covered by the root-validation + marker
fix here, so it becomes a re-verification.

## Step 9

Post-implementation: commit code (`bug: ... (t1283)`), commit plan via
`aitask_task_commit.sh`, archive per task-workflow Step 9.

## Risk

### Code-health risk: medium
- A dir store created before this change (no marker) stops working until `ait artifact init-store dir` is run once. Intended fail-closed behaviour; the error names the exact remedy, and the only such store is the t1142 verification share · severity: low · → mitigation: none needed (actionable error message is part of the plan)
- Rollback hooks run inside the chained EXIT trap; a backend op that exits there would leak the attach lock. Addressed by the delete-returns contract + the fault-injection test · severity: high · → mitigation: in plan (step 1 delete contract, step 5 fault injection)
- Concurrent unmount between validation and `put`'s shard write is not protected · severity: medium · → mitigation: dir_put_concurrent_unmount_guard
- New `init` op in the backend contract: a future adapter that omits it fails with "command not found" instead of a clean message · severity: low · → mitigation: none needed (extension-point comment updated in step 2)

### Goal-achievement risk: low
- The marker proves "this is an initialized aitasks store", not "the store this config meant". A wrong path pointing at a *different* initialized store would still be accepted. Neither observed defect needs more, and this is out of scope · severity: low · → mitigation: none needed

### Planned mitigations
- timing: after | name: dir_put_concurrent_unmount_guard | type: bug | priority: medium | effort: medium | inline_risk: medium | added_complexity: medium | addresses: concurrent unmount between validation and put's shard write | desc: Keep every dir put filesystem operation (shard mkdir, temp file, final mv) tied to the validated root itself (e.g. an fd / cwd held on the validated directory plus relative paths), never re-resolved by pathname; acceptance = a test that makes the share disappear between validation and mutation and shows no shard, temp file or blob lands in the underlying mountpoint; pathname re-checks (marker or device/inode) are out (TOCTOU)

## Post-Review Changes

### Change Request 1 (2026-10-12)
- **Requested by user:** `artifact_dir_init` accepted a directory squatting on the marker name — `mv -f tmp <dir>` moved the staged temp inside it and init printed INITIALIZED (exit 0) for a store every op still refuses, leaving nested temps on repeated runs.
- **Changes made:** init now refuses any non-regular-file at the marker path before staging (left untouched, actionable message), and installs the marker via `ait_atomic_commit` (lib/atomic_write.sh), whose directory check discards the temp on the race. A bare `mktemp` is kept instead of `ait_atomic_tmp` because the latter `mkdir -p`'s the parent (= the store root, which must never be created). Tests: squat directory (two attempts, no success claimed, dir preserved, no temp residue, store still refused), the `ait_atomic_commit` race guard, and the CLI path.
- **Files affected:** `.aitask-scripts/lib/artifact_backends/dir.sh`, `tests/test_artifact_dir_backend.sh`, `tests/test_artifact_share_resolution.sh`

## Final Implementation Notes
- **Actual work done:** As planned: `dir.sh` validates the store root in the op's own shell (`_artifact_dir_check_root` / `_artifact_dir_require_root`), never derives a blob path from an empty root, requires the `.ait-artifact-store` marker, and `artifact_dir_delete` returns (never dies). New contract op `artifact_backend_init` (dir: writes the marker, never creates the root; local: no-op) and verb `ait artifact init-store <backend>`. Docs: seed `project_config.yaml` dir comment, `aidocs/unified_artifact_design.md` §6.
- **Deviations from plan:** (1) `lib/txn_snapshot.sh` `txn_rollback_report` now ends with an explicit `return 0` — not in the plan, but required for the lock-release property: J5 (die mid-transaction → rollback from the EXIT trap) still leaked the attach lock with the returning delete. (2) `tests/test_attach_lock_callback_contract.sh` allowlist line numbers moved +6 (header comment + help lines shifted the four `aitask_artifact.sh` sites; the allowlist is line-keyed by design). (3) Two more fixtures needed `init-store dir`: `test_attach_lock_callback_contract.sh`, `test_attach_txn_worktree_isolation.sh`. (4) Rollback fault injection covers both routes: J4 (commit failure → `txn_abort`) and J5 (python-shim fault → EXIT trap).
- **Issues encountered:** `txn_rollback_report`'s trailing `[[ $_TXN_SNAP_RESTORE_INCOMPLETE == true ]] && echo` returned 1 whenever only a rollback HOOK recorded a failure; called from `_txn_exit_trap` under the script's errexit, that aborted the trap before snapshot cleanup and the chained `registry_lock_release`. Previously unreachable for dir (delete silently "succeeded" via `rm -f /<2>/<62>`). Pinned by `test_txn_snapshot.sh` C5.
- **Key decisions:** marker written only by explicit `init-store` (never at first use — the first use of an empty unmounted mountpoint is the trap); validation in the ops, not at activation, so warm-cache offline `get` keeps working; validation boundary (op entry only) documented in `dir.sh` and §6, concurrent unmount deferred to the planned "after" mitigation.
- **Red proofs:** pre-fix `dir.sh` (+minimal init) fails 17 lib / 13 e2e checks; a dying delete fails J4/J5 incl. the J5 lock leak; the old report fails C5 and the J5 lock checks; the old init fails 7 lib / 3 e2e squat checks.
- **Upstream defects identified:** `.aitask-scripts/lib/txn_snapshot.sh:240-241 — txn_rollback_report returned 1 on a hook-only incomplete rollback, aborting _txn_exit_trap under errexit and leaking the attach lock (fixed in this task)`
