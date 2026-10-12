---
Task: t1286_artifact_rm_skips_local_blob_sweep_when_backend_moved.md
Base branch: main
Output branch: main
---

# t1286 — `ait artifact rm` sweeps local blobs regardless of the manifest's current backend

## Context

`_artifact_rm_txn` (`.aitask-scripts/aitask_artifact.sh`, ~line 652) wraps the whole
orphan-blob sweep in `if [[ "$backend" == "local" ]]`. After the normal lifecycle
`create --backend local` → `move --to dir` (move deliberately keeps the source blobs)
→ `rm`, the manifest says `dir`, so the sweep is skipped: `rm` prints
`0 orphan blob(s) swept` and the git-tracked local blobs stay on the data branch
forever. The decision must key off where each blob lives, not off the manifest's
current backend. The `dir`-side leak stays the documented t1135 gap and must keep
being reported.

## Implementation

### 1. `.aitask-scripts/aitask_artifact.sh` — `_artifact_rm_txn` last-reference sweep

Replace the `if local … else warn … fi` block with a backend-independent, two-pass
local sweep (select → preflight all → delete) followed by the unchanged non-local
warning:

```bash
    local del_paths=( "$task_file" "$manifest_rel" )
    local swept=0 remaining="" scanned=0 h blob_rel doomed=()
    # Local blobs are swept whatever the manifest's CURRENT backend is: `move`
    # keeps its source blobs, so an artifact created on `local` and moved away
    # still owns git-tracked blobs here (t1286).
    artifact_registry_activate local
    # Pass 1 — select: present on disk, not owned by an attachment, not
    # referenced by any remaining manifest (on any backend).
    for h in ${versions[@]+"${versions[@]}"}; do
        [[ -f "$(attach_meta_dir)/$(artifact_shard_path "$h").json" ]] && continue
        artifact_local_head "$h" || continue
        if (( ! scanned )); then
            # (existing comment about the fail-closed scan, kept verbatim)
            remaining="$(artifact_manifest referenced-hashes)" \
                || txn_abort "ait artifact rm: could not compute remaining manifest references (…same message…)"
            scanned=1
        fi
        printf '%s\n' "$remaining" | grep -qxF "$h" && continue
        doomed+=( "$h" )
    done
    # Pass 2 — preflight EVERY candidate before deleting ANY. The rollback hook
    # restores a swept blob with reset + checkout, i.e. the COMMITTED bytes, so
    # deletion is only recoverable for a blob that is clean against HEAD. Index
    # membership is not enough: an unstaged/staged edit would be lost, and a
    # staged addition absent from HEAD could not be restored at all.
    # txn_require_clean refuses all of those (and plain untracked blobs). It is
    # NOT a recovery proof on its own: `git status --porcelain` is silent for an
    # IGNORED untracked file, which has no committed copy at all. So each
    # candidate must also exist in HEAD with exactly its on-disk bytes (same
    # git object id) — the committed copy the rollback hook would check out.
    # Every refusal dies; the armed trap restores the already-patched task file
    # and deleted manifest, and no blob has been touched yet.
    local head_oid disk_oid
    for h in ${doomed[@]+"${doomed[@]}"}; do
        blob_rel="$(artifact_local_blob_relpath "$h")"
        txn_require_clean "ait artifact rm" "$blob_rel"
        head_oid="$(task_git rev-parse -q --verify "HEAD:${blob_rel}")" \
            || die "ait artifact rm: ${blob_rel} has no committed copy on the data branch, so deleting it could not be rolled back — commit it or move it aside, then re-run"
        disk_oid="$(task_git hash-object -- "$blob_rel")" \
            || die "ait artifact rm: could not hash ${blob_rel} — refusing to delete a blob whose recovery cannot be verified"
        [[ "$disk_oid" == "$head_oid" ]] \
            || die "ait artifact rm: ${blob_rel} differs from its committed copy, so deleting it would lose bytes — restore or commit it, then re-run"
    done
    # Pass 3 — delete.
    for h in ${doomed[@]+"${doomed[@]}"}; do
        blob_rel="$(artifact_local_blob_relpath "$h")"
        artifact_backend_delete "$h" \
            || die "ait artifact rm: could not delete the orphaned blob $h"
        _ARTIFACT_TXN_SWEPT_BLOBS+=( "$blob_rel" )
        del_paths+=( "$blob_rel" )
        swept=$((swept + 1))
    done
    if [[ "$backend" != "local" ]]; then
        warn "backend '${backend}' is not local — its backend blobs were not deleted (cross-backend orphan reaping is t1135)"
    fi
```

Notes:
- **Candidate safety (two review concerns, both verified valid):**
  1. The `ls-files --error-unmatch` guard from the first draft proved index
     membership only. `txn_require_clean` (`lib/txn_snapshot.sh:104`) refuses
     unstaged/staged edits, staged additions and plain untracked blobs, which
     preserves the user's bytes and staging state.
  2. `git status --porcelain` says nothing about an **ignored** untracked file
     (verified in a scratch repo: status empty, `rev-parse HEAD:<path>` fails).
     So each candidate also needs an explicit recovery proof: `HEAD:<blob_rel>`
     must exist, and `git hash-object` of the on-disk file must equal its object
     id. Then the bytes being deleted are byte-for-byte the copy
     `_artifact_rollback_rm_blobs` checks out. Comparing object ids also covers a
     tracked path whose worktree drift is hidden from status (skip-worktree /
     assume-unchanged).
  Both checks run only on actual deletion candidates, after the keep-guards (a
  dirty blob that is KEPT never blocks rm), and over **every** candidate before
  **any** deletion, so a refusal leaves no blob touched and only the task file and
  manifest need restoring (done by the armed trap). Policy is **refuse** (fail
  closed with an actionable message), never a silent skip, so a doomed blob is
  never quietly left behind with a misleading swept count. This also closes the
  same weakness on the pre-existing local-backend path, which now shares the code.
- The reference scan is run lazily (only once there is a present candidate), so a
  non-local rm with no local blobs keeps its current behaviour and is not newly
  blocked by an unrelated malformed manifest. With a candidate the scan still runs
  and still fails closed — F10 and `test_attach_txn_worktree_isolation.sh` R8 both
  have a present, committed candidate, so they still reach it.
- Swept count now counts only blobs actually removed, satisfying "reported swept
  count matches what was actually removed". For a local-backend artifact every
  blob is committed at create/update, so its normal behaviour is unchanged.
- Warning keeps the `not local` / `t1135` wording; only "backend blobs" → "its
  backend blobs" for clarity (no test greps that text today).
- The keep-guards (attachment meta file, any remaining manifest referencing the
  hash) are unchanged; a hash still referenced by a manifest on any backend keeps
  its local blob (conservative).

### 2. `tests/test_artifact_cli.sh` — new section J (create-local → move-to-dir → rm)

Appended before the summary footer (no subshells; the file uses plain counters):

- Register a `dir` backend: write `aitasks/metadata/project_config.yaml` with
  `attachments_gc_grace: 0` + `artifacts: backends: dir: path: $TMP/store` (same shape
  as `tests/test_artifact_share_resolution.sh` `write_config`, without
  `default_backend`), and commit it.
- `create 5 mv1.txt --kind report --handle art:t5-mv --backend local`, then
  `update art:t5-mv mv2.txt` → hashes HV1, HV2, both blobs present + tracked.
- Negative control: `create 6 mv1.txt --kind report --handle art:t6-mvshare` (shares HV1
  on local).
- `move art:t5-mv --to dir`; assert manifest backend is `dir` and both local blobs
  still exist (move keeps source blobs).
- `rm 5 art:t5-mv`, capture output + rc:
  - exit 0; output contains `1 orphan blob(s) swept`;
  - output still contains `not local` and `t1135` (dir-side gap reported);
  - HV2 local blob gone and not tracked (`git ls-files` empty);
  - HV1 local blob KEPT (referenced by `art:t6-mvshare`);
  - dir-store copies of HV1/HV2 still present (t1135 gap unchanged);
  - `git status --porcelain -- attachments/ artifacts/ aitasks/` clean (deletions
    committed).
- Update the file's header comment to mention the cross-backend rm case and the
  dirty-candidate refusal.

### 2b. `tests/test_artifact_cli.sh` — section K: unsafe candidates are refused

Each case: create an artifact on `local`, `move` it to `dir` (the newly-swept
path), make its only local blob unsafe, then `rm`. A shared helper asserts the
refusal contract: rc ≠ 0; output names the blob path and "uncommitted changes";
frontmatter entry still listed (`ait artifact ls`); manifest file restored and
still `"backend": "dir"`; `git status --porcelain -- aitasks/ artifacts/` empty.

- **K1 unstaged edit:** append bytes to the blob file. Assert after refusal: blob
  bytes are still the edited bytes (cmp against a saved copy), status still ` M`.
- **K2 staged edit:** append bytes and `git add` the blob. Assert: edited bytes
  kept, status still `M ` (staging state intact).
- **K3 staged addition absent from HEAD:** `git rm -q --cached <blob>` + commit
  (blob now untracked in HEAD), then `git add <blob>`. Assert: blob present with
  original bytes, status still `A ` (not reset away).
- **K4 untracked:** same as K3 without the final `git add`. Assert: blob present,
  status still `??`.
- **K5 ignored untracked (absent from HEAD):** same as K4, then append the blob's
  path to `.git/info/exclude` (so `status --porcelain` is empty, which is the
  trap). Assert: rc ≠ 0; output says "no committed copy"; blob bytes preserved
  (cmp against saved copy); task entry and manifest restored. Remove the exclude
  line afterwards. Run this case first with the HEAD/hash-object checks commented
  out to confirm it would lose the blob (red proof), then restore them.

The shared refusal helper asserts on the generic "uncommitted changes" text for
K1–K4 and takes the expected message as a parameter so K5 can pass "no committed
copy".

Then a positive control: restore K1's blob to clean (`git checkout -- <blob>`), re-run
`rm` → succeeds, `1 orphan blob(s) swept`. This shows the refusal comes from the
dirty state and not from some other cause.

Red proof: K1–K3 against the first-draft (`ls-files`) logic would lose bytes or
staging; confirm K1 fails against an implementation with the preflight loop
commented out, then restore it.

Red proof: run the new section against the unmodified script first and confirm it fails
(`0 orphan blob(s) swept`, HV2 blob still present), then apply step 1.

### 3. Step 9 (Post-Implementation)

Commit code (`bug: … (t1286)`), then archival/merge per task-workflow Step 9.

## Verification

- `bash tests/test_artifact_cli.sh` — all pass (new J + existing F2/F4/F5/F10/I).
- `bash tests/test_artifact_share_resolution.sh`, `bash tests/test_attach_txn_worktree_isolation.sh`,
  `bash tests/test_attach_lock_callback_contract.sh` — unchanged pass.
- `shellcheck .aitask-scripts/aitask_artifact.sh`.

## Risk

### Code-health risk: low
- Behaviour change on the local-backend path: a version whose local blob is missing is no longer counted, and a dirty/untracked unreferenced blob now refuses the rm (rolled back) instead of being deleted (edits lost) or failing the commit. Strictly safer; existing rm tests pin the normal path · severity: low · → mitigation: none needed (covered by section K + the F-section + R8 runs)
- A user with a dirty unreferenced blob is blocked until they commit or revert it. Same refusal contract as every other path these verbs stage, and the message says what to do · severity: low · → mitigation: none needed
- The reference scan now runs lazily, only when a local candidate exists · severity: low · → mitigation: none needed (F10 and R8 still exercise the fail-closed path)

### Goal-achievement risk: low
None identified.
