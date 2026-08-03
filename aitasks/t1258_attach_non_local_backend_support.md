---
priority: medium
effort: high
depends: [1231]
issue_type: feature
status: Ready
labels: [task_attachments]
gates: [risk_evaluated]
anchor: 1065
created_at: 2026-07-26 22:59
updated_at: 2026-07-26 23:00
boardidx: 37888
---

## Origin

Risk-mitigation ("after") follow-up for t1231, created at decomposition time.
t1231 was split into children, so its Step 8d never runs — the mitigation is
created here instead, with `depends: [1231]` preserving the "after" ordering.

## Risk addressed

Goal-achievement risk (severity: medium) from `p1231`:

> The task says "artifact/attachment blob store", but `ait attach` hard-rejects
> non-local backends, so v1 delivers artifacts only.

t1231 ships the `gitbranch` artifact backend, but **attachments cannot use it**:

- `.aitask-scripts/aitask_attach.sh:225` — `cmd_add` hard-rejects anything but
  `local`: `[[ "$backend" == "local" ]] || die "ait attach add: backend
  '$backend' not yet supported (local only in t1030_2)"`.
- `aitask_attach.sh:599` — `_attach_gc_txn` hard-codes
  `export ARTIFACT_BACKEND="local"` with the comment "v1 is local-only; add
  rejects other backends, so every stored blob is local".
- `aitask_attach.sh:234, 326` — backend selection is a bare
  `export ARTIFACT_BACKEND=...`; it does **not** go through
  `artifact_registry_activate`, so no config validation happens.
- `aitask_attach.sh:275, 301, 603` — blob staging calls
  `artifact_local_blob_relpath` unconditionally, which is only meaningful for the
  data-branch-resident `local` backend.

## Goal

Extend `ait attach` to non-local backends so attachments can live on the same
storage as artifacts (`dir`, `gitbranch`, and later `s3`/`gdrive`).

Scope to work through:

1. **Registry-based selection** — replace the bare `export ARTIFACT_BACKEND` in
   `_attach_add_txn` / `cmd_get` / `_attach_gc_txn` with
   `artifact_registry_activate`, so unregistered names fail closed the same way
   artifacts do.
2. **Add path** — drop the local-only rejection; stage the blob relpath only when
   the backend's blobs live on the data branch (the same predicate
   `aitask_artifact.sh` already applies at its seven `backend == local` sites).
3. **Per-blob meta ledger** — `attachments/meta/<2>/<62>.json` stays on the data
   branch regardless of backend (it is a refcount ledger, not a blob), but its
   `backend` field must record the real backend so gc can route deletion.
4. **gc** — `_attach_gc_txn` must activate the backend recorded in each orphan's
   meta file rather than assuming `local`, and must handle the case where a
   backend cannot delete (warn, do not silently drop the refcount).
5. **Coordinate with t1135** (artifact manifest lifecycle / orphan reaping) —
   `aitask_artifact.sh:553` already defers cross-backend orphan reaping there;
   make sure the two do not implement conflicting sweep semantics.

## Verification

- Round-trip `ait attach add/get/rm/gc` against `dir` and `gitbranch` backends.
- `local` behavior stays byte-identical: `bash tests/test_attach_local_backend.sh`,
  `bash tests/test_attach_archive_gc.sh`,
  `bash tests/test_attach_gc_manifest_blocking.sh` all still pass unchanged.
- gc on a non-local backend deletes the backend blob and the meta file together,
  with the existing commit-failure rollback intact.
