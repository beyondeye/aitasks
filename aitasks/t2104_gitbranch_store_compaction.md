---
priority: medium
effort: high
depends: [2102]
issue_type: feature
status: Ready
labels: [task_attachments]
gates: [risk_evaluated]
anchor: 1065
created_at: 2026-10-21 14:52
updated_at: 2026-10-21 14:52
---

## Context

Decided in t1890 (`aidocs/artifact_storage_lifecycle.md`, D4, §6, **§7
compaction safety contract**, §8 purge scope): storage held by the `gitbranch`
store is reclaimed by **compacting the store**, never by rewriting
`aitask-data`.

**Today** gitbranch `delete` only adds a commit removing the path
(`gitbranch.sh:387-390, 504-514`), so the bytes stay in branch history; `rm`
never deletes non-local blobs (`aitask_artifact.sh:894-896`). `gitbranch-migrate`
(`aitask_artifact.sh:1034-1232`) copies **every** blob to a new branch and fences
the old one with `.ait-artifact-retired`. That is safe because it filters
nothing, and it does not make a *filtered* copy safe.

**Why the live set in one checkout is not proof that a blob is garbage:**
`create` / `update` publish the blob to the store (`aitask_artifact.sh:429`,
`:547`) before the manifest is committed, and the data branch is pushed
separately. Another clone can hold a published blob whose manifest the
compacting clone cannot see yet.

Depends on t2102 (pin/prune): the live set includes pinned and non-expired
versions.

## Scope: `ait artifact compact-store` (preview by default, `--apply` to run)

Implements the §7 contract exactly:

1. **Fresh references.** Fetch `aitask-data` and refuse unless the local data
   branch equals the remote tip.
2. **Live set.** Every version in every manifest (including pinned; excluding
   expired) plus every attachment-meta hash, at that tip.
3. **Age-based eligibility.** A blob may be excluded only if the store commit
   that added it is older than `artifacts_compaction_grace` (new key, default
   `30d`, parsed like `attachments_gc_grace`). Within the grace window it is
   always carried forward.
4. **Preview and backup.** The preview shows counts and bytes: kept, excluded,
   carried forward because of grace. `--apply` writes a backup ref first.
5. **Rebuild.** Build a fresh-root store holding the kept blobs on a **new**
   branch, reusing the migrate copy + verify + CAS-push machinery. Retire the old
   branch with the existing fence; it stays readable.
   - **Read fallback:** a version missing in the compacted store is read from the
     retired predecessor while the predecessor exists.
6. **`--delete-retired`** is a separate explicit step, allowed only after the
   grace window. It re-fetches `aitask-data`, runs the **late-reference sweep**
   (copies forward any blob that a now-visible manifest or attachment
   references), prints the coordination requirement and the number of blobs it
   is about to make unreachable, and then deletes the retired branch on the
   remote.
7. **One retirement at a time.** Refuse a new compaction while a retired
   predecessor still exists. The message names the pending branch and the
   earliest time `--delete-retired` is allowed.
8. Also refuse while the local store is ahead of the remote (unpublished writes;
   coordinate with t1259's offline queue).

## Verification (tests, two scratch clones over `file://`)

- **Two-clone withheld manifest.** Clone Y publishes a blob and withholds its
  manifest commit through compaction in clone X.
  - Inside the grace window, the blob is carried forward.
  - With the grace window forced to `0`, it is excluded. But after Y pushes the
    manifest, Y's `get` succeeds through the retired fallback, and
    `--delete-retired` copies the blob forward rather than losing it.
- **Two compactions, delayed manifest, cold cache.**
  1. Y publishes a blob and withholds its manifest.
  2. X compacts store A into B with grace `0`, so the blob is excluded.
  3. X's second compaction (B into C) is refused, naming retired branch A.
  4. Y pushes the manifest.
  5. X clears `~/.cache/ait/artifacts` and runs `get`; it succeeds through A.
  6. `--delete-retired` copies the blob forward into B and deletes A.
  7. Compaction B into C runs, and a cold-cache `get` succeeds from C.
- A concurrent write during compaction loses nothing (the CAS fence).
- **Old clone resynchronization**: a stale clone refuses or follows the fallback
  and never writes to the retired store.
- A preview / dry run changes nothing.

## Docs

- `website/content/docs/commands/artifact.md`: a `compact-store` section with
  the purge scope (§8).
  - No command in one checkout erases copies in other clones, forks or backups.
  - Hosted remotes decide when unreachable objects are collected.
  - The coordination requirement (do not keep manifest commits unpushed across a
    `--delete-retired`).
