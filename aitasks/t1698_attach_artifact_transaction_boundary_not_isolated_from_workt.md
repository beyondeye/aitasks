---
priority: high
effort: medium
depends: [1675]
issue_type: bug
status: Ready
labels: [bash_scripts, robustness, data_integrity]
gates: [risk_evaluated]
anchor: 1661
followup_kind: review_finding
created_at: 2026-09-02 22:18
updated_at: 2026-09-02 22:18
---

## Origin

Split out of t1675 during planning, at the user's direction. t1675 stays focused
on its own bug (`with_attach_lock` suppresses errexit, so a failed mutation is
reported as success). The three issues below were discovered *while* auditing
that seam, are independent of it, and are all **pre-existing** — they reproduce
on today's tree with no t1675 change applied.

They are grouped here because they share one root cause (**the attach/artifact
transaction boundary is not isolated from the worktree**) and one fix surface.

## The three defects (all measured, not inferred)

Fixture in every case: a legacy-mode git repo (`_ait_detect_data_worktree`
returns `.`, `task_git` passes through to plain git), one task `t5_demo`, one
small file attached.

### 1. A successful commit ABSORBS an unrelated in-flight edit

`_attach_commit` / `_artifact_commit` run `task_git add -- "$path"`, which stages
the **whole file**. Path-scoping the commit does not help when the path itself is
dirty.

Measured — with an unrelated uncommitted edit in flight on `aitasks/t5_demo.md`,
a **fully successful** `ait attach add`:

```
add exit=0
b08027c ait: Attach f1.bin to t5
 aitasks/t5_demo.md   | 10 ++++++++++
--- diff of the attach commit for the task file ---
  +attachments:
  +  - hash: sha256:95cc8e8e...
  ...
  +USER EDIT IN FLIGHT          <-- absorbed
occurrences in HEAD: 1
```

The user's unrelated work is published under an `ait: Attach …` commit message.
Once it is in HEAD, no rollback can undo it.

**Not limited to task files.** The hazard is whole-path staging, so it applies to
every pre-existing mutable path a transaction stages: attachment meta JSON in
`add` / `rm` / `gc` / `decref-deleted`, and artifact manifests in `create` /
`update` / `move` / `rm`. `ait artifact update` is the sharp case — it never
touches task frontmatter (the stable-handle/mutable-manifest split), but it
stages `manifest_rel`, and `artifact_manifest set-current` read-modify-writes
that JSON.

Blob paths are NOT affected: a blob's path is its content hash, so there is
nothing to absorb.

### 2. Rollback DESTROYS an unrelated in-flight edit

The existing rollbacks are `task_git reset` + `task_git checkout -- <path>` —
restore-from-**HEAD**, which discards any pre-existing dirty state on a
transaction-owned path. The attach lock does not help: it excludes other attach
ops, not the human or agent session that edited the task file moments earlier.

Measured — uncommitted edit in flight, commit forced to fail via a `pre-commit`
hook, so the **existing** commit-failure rollback runs:

```
before: 1 user-edit line(s)
Error: ait attach add: commit failed — rolled back to pre-attach state
add exit=1
after : 0 user-edit line(s)     <-- silently destroyed
```

### 3. A post-mutation abort leaves uncommitted ledger drift

Today the rollback lives *inline inside the commit-failure branch only*
(e.g. `aitask_attach.sh:359-362` in `_attach_rm_txn`). Once t1675 lands its
`|| die` guards, an abort can happen after a mutation but before the commit —
e.g. a successful `attach_meta decref` followed by a failing
`frontmatter_patch.py remove` leaves the ledger decremented on disk with the task
frontmatter untouched.

t1675 deliberately does **not** paper over this with a HEAD restore: doing so
would multiply defect 2's trigger points from one to a dozen. t1675 stops the
false *success*; this task owns the residual on-disk state.

## Scope

1. **Shared transaction-boundary infrastructure.** Do not write it from scratch —
   `aitask_fold_mark.sh:428-489` already carries a correct facility that t1668
   built for exactly this: `_fold_snap_init` / `_fold_snap_add` /
   `_fold_restore_snapshots` capture each path's pre-mutation **bytes** *and* its
   full `ls-files --stage` index entry (every stage, so an unmerged path
   round-trips), represent absence explicitly so a transaction-created path is
   deleted on restore, and fail closed on an unreadable index. Promote it to
   `.aitask-scripts/lib/txn_snapshot.sh` under neutral names; `aitask_fold_mark.sh`
   sources the lib and drops its private copies. One implementation, not two.

2. **Defect 1 — preflight.** Refuse to start when any pre-existing non-blob path
   the transaction will stage is dirty (`txn_require_clean`), with an actionable
   message naming the path and the remedy. Fail closed; do **not** stash and
   reapply (reapplying hunks around a commit can conflict, and stashing in a
   shared worktree is the very hazard here).

3. **Defect 2 + 3 — rollback.** Every transaction gets a named rollback helper
   invoked from **every** abort path, not just the commit-failure branch,
   restoring pre-transaction bytes and index entries via the promoted facility —
   never HEAD. Blob paths keep HEAD restore (content-addressed; snapshotting
   would copy up to 25 MB per blob and gc sweeps many).

   Invariant: **a transaction either commits completely, or restores its own
   paths to their pre-transaction bytes and index entries.**

## Design constraints found during the t1675 audit

These were established by inspection and are easy to get wrong:

- **Placement: at the verbs, never in the seam.** `ait fold` writes task files in
  its Steps 4-5 and commits only at Step 6, so at its Step 5b attach transaction
  those files are *legitimately dirty with the fold's own work*. A preflight
  inside `with_attach_lock`, `_attach_commit`, or the shared helpers breaks
  `ait fold` outright. Fold reaches only `_fold_attach_txn`, never the eight verb
  paths, and already snapshots the whole meta tree.

- **Path discovery differs by verb.** `meta_rel` / `manifest_rel` are pure
  functions of the hash / handle, so `attach add|rm` and `artifact
  create|update|move|rm` can check at entry, before `with_attach_lock`.
  `attach gc` and `attach decref-deleted` discover paths as they iterate and must
  check immediately before each path's first mutation.

- **Once per path, but with TWO independent sets.** `_attach_decref_deleted_txn`
  decrefs per `(task_id, hash)` on purpose ("a blob shared by two doomed tasks
  must lose BOTH refs") and dedups only its *staging* list (`seen_relpath`), not
  the ops — so two doomed tasks sharing one attachment reach the same meta JSON
  twice. Without dedup, the second `txn_require_clean` sees the transaction's own
  first decref as dirt and refuses a valid operation, and a second `txn_snap_add`
  overwrites the pre-transaction bytes with post-mutation ones (restore replays
  in index order, so the later snapshot silently wins).

  A **single** `seen` set is unsound: clean-check first would mark the path and
  make the snapshot skip, leaving nothing to restore; snapshot first would mark
  it and make the clean check skip, letting a dirty path be committed. Use two
  independent sets (`_txn_clean_checked`, `_txn_snapshotted`) reset by
  `txn_snap_init`, so the helpers are order-independent.

## Verification

- **`tests/test_txn_snapshot.sh` (new, lib-level).** Round-trip: a staged path
  comes back staged with the same blob; an unstaged-but-modified path comes back
  with its bytes; a path with no index entry stays out (`--force-remove`); a
  transaction-created path is deleted on restore; an unreadable index fails
  closed rather than recording "absent"; a second `txn_snap_add` after mutation
  is a no-op so restore yields pre-transaction bytes. Plus both **ordering**
  tests: `txn_require_clean` -> `txn_snap_add` still snapshots, and
  `txn_snap_add` -> `txn_require_clean` still refuses an entry-dirty path.

- **Dirty-worktree pins, success path (no fault injected).** Refused: `attach
  add` with a dirty task file (unstaged AND staged); `attach rm` with dirty meta
  JSON; `artifact update` / `move` with a dirty manifest; `artifact create` /
  `rm` with a dirty task file; `attach gc` with a dirty meta JSON on a sweep
  candidate. Still succeeding: `artifact update` / `move` with a dirty **task
  file** (manifest clean — the stable-handle split, asserted not assumed);
  `attach decref-deleted` with two doomed tasks sharing one attachment (the
  dedup case); `ait fold` with attachments and its own dirty task files.

- **Dirty-worktree pins, abort path (fault injected).** Each asserts non-zero
  exit, no success message, zero commits added, and the transaction's paths
  byte-identical to their pre-command state. Include the recorded defect-2 case
  (dirty file + forced commit failure, no python fault) — it **fails on today's
  tree**, so it is the regression proof.

- Fault injection uses the documented `AIT_PYTHON` override with a passthrough
  shim that fails a named script + subcommand, with an occurrence index ("fail
  the Nth call") so a fault can be placed after earlier mutations in a loop —
  the only way to reach a rollback helper's non-trivial restore path. t1675
  builds this shim; reuse it.

- **Pre-fix control, per pin (mandatory).** Run each pin against a scratchpad
  copy of the unfixed scripts and confirm it fails there. A pin that passes both
  ways proves nothing. The trap is systematic in this code: several transactions
  stage a path the failed mutator was supposed to create, so `git add` fails and
  the pre-fix run *appears* correct for the wrong reason.

- Regression net: `test_fold_mark.sh` (required — it is the real-entry-point
  proof that the promoted facility still behaves), plus
  `test_attach_local_backend.sh`, `test_attach_meta.sh`,
  `test_attach_archive_gc.sh`, `test_attach_gc_manifest_blocking.sh`,
  `test_attach_task_delete_decref.sh`, `test_attach_fold_rebind.sh`,
  `test_attachment_meta_lib.sh`, `test_artifact_cli.sh`,
  `test_artifact_dir_backend.sh`, `test_artifact_fold_transfer.sh`,
  `test_artifact_share_resolution.sh`, `test_artifact_manifest_lib.sh`,
  `test_attach_lock_callback_contract.sh` (t1675's).

  Re-check `test_attach_local_backend.sh` section G, which stages an *unrelated*
  file — outside the transaction's paths, so it must still pass.

## Note on user-visible behaviour

The preflight makes previously-working invocations fail across all eight verb
paths: an attach/artifact command on a dirty path it would stage now refuses
instead of absorbing the edit. That is deliberate and is the point of the fix,
but it is a real behaviour change and the message must name the path and the
remedy.
