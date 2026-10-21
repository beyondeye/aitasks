---
priority: medium
effort: high
depends: [1135]
issue_type: feature
status: Ready
labels: [task_attachments]
gates: [risk_evaluated]
anchor: 1065
created_at: 2026-10-21 14:51
updated_at: 2026-10-21 14:51
---

## Context

Decided in t1890 (`aidocs/artifact_storage_lifecycle.md`, D3 and §5/§6): nothing
expires automatically, and older versions are removed only by an explicit prune
that protects evidence. **Today** manifests are append-only and nothing prunes
them (`lib/artifact_manifest.py:215-219`; the comments at `:47, 252-253` and
`aitask_attach.sh:618-623` refer to version pruning that was never implemented).
The schema (`artifact_manifest.py:13-29`) has no pinning, no tombstones and no
per-version timestamps.

Depends on t1135 (manifest lifecycle on hard delete and the orphaned-manifest
reaper), whose orphan sweep this task reuses for local blobs.

## Scope

1. **Manifest schema extension** (follow
   `aidocs/framework/aitasks_extension_points.md`; keep old manifests readable):
   - `pinned: [<hash>…]`;
   - `expired: [{hash, expired_at, by}]` tombstones;
   - optional per-version `added_at`, if needed for `--older-than`. A version
     without it is treated as having an unknown age and is never pruned by age
     alone.
2. Verbs:
   - `ait artifact pin <task> <ref> [--version <hash>]` (default: current) and
     `unpin`.
   - `ait artifact prune <task> <ref> | --all [--keep N] [--older-than DUR]
     [--include-archived] [--apply]`. **The default is a dry-run report**: what
     would expire, and why every other version is kept.
3. **Protection rules.** prune never expires:
   - the current version;
   - a pinned version;
   - a hash referenced by any other manifest version or any attachment meta
     (shared blob);
   - any version of an artifact with **at least one** archived owner (a loose
     or bundled archived task), even one shared with active tasks, unless
     `--include-archived` is given.
4. **On `--apply`:**
   - move the hash from `versions` to `expired` with a tombstone;
   - sweep newly orphaned **local** blobs through t1135's sweep (same HEAD-clean
     preflight as `rm`);
   - leave non-local orphans for store compaction (t2104) or
     backend-specific reaping.
   - One commit, under `with_attach_lock`, with rollback.
5. **A pin outlives owner removal** (design doc D3, §5). Nothing removes a
   pinned version or deletes its manifest while it is pinned. Extend every
   path that can drop a manifest:
   - `ait artifact rm` of the **last** reference (`aitask_artifact.sh`
     ~L785-903) refuses when any version is pinned, naming `ait artifact
     unpin`. An explicit `--unpin` flag unpins and removes in one step.
   - t1135's hard-delete decref refuses in the same way, so the hard delete
     needs an explicit choice.
   - t1135's orphaned-manifest reaper skips pinned manifests and lists them
     in its report.
   - Store compaction (t2104) already counts pinned hashes as live.
6. `ait artifact get --version <expired hash>` reports *expired* (at, by)
   instead of *not found*. `versions` lists expired entries distinctly.

## Verification (tests)

- **Shared-blob retention**: two artifacts share a hash, and pruning one keeps
  the blob.
- **Archived / pinned evidence**: a pinned version and an archived-only artifact
  survive `prune --all --apply`; `--include-archived` expires the archived one's
  unpinned history.
- **Version expiry + tombstone**: `get` of an expired version reports expired;
  a dry run changes nothing.
- **Concurrent prune vs. update** of the same artifact under the lock: no lost
  version, no half-written manifest.
- **Mixed active/archived ownership**: one manifest is owned by an active
  task and an archived task, and has an unpinned historical hash used by no
  other manifest. `prune --all --apply` keeps the hash; with
  `--include-archived` it expires.
- **Pin outlives owner removal**: with a version pinned, `rm` of the last
  reference refuses and the manifest and blob remain; hard-delete refuses;
  the reaper skips and reports the manifest. `rm --unpin` removes it.
- Old manifests without the new fields still load.

## Docs

- `website/content/docs/commands/artifact.md`: `pin`, `unpin`, `prune` sections.
- The lifecycle states in `concepts/artifacts.md`.
