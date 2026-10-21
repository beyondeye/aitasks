# Artifact & Attachment Storage Lifecycle

The agreed policy for where artifact and attachment bytes live, what a new
machine downloads, how long evidence is kept, and how storage is reclaimed.
Decided with the user in t1890 (2026-10-21). It extends §9 of
[`unified_artifact_design.md`](unified_artifact_design.md) and §8 of
[`task_attachments_design.md`](task_attachments_design.md). Artifacts and
attachments share one content-addressed blob namespace, so the policy covers
both.

Status: **decided design**. Most of the mechanisms below are not implemented
yet. §10 maps each one to the task that delivers it. Statements about the
current behaviour are marked **today**.

## 1. Two separate questions

The two questions get separate answers. Mixing them up leads to wrong fixes,
such as running `git gc` to make a clone smaller.

1. **What does a fresh computer download?** This is a property of *where the
   bytes live and which refs a routine fetch follows* (§2, §3).
2. **How do we reclaim storage for evidence we no longer need?** This is a
   property of *retention, reference checks, and what removing a reference
   actually frees* (§5, §6, §7).

A clean task-data branch is not the same thing as a small clone. Moving new
blobs off `aitask-data` keeps its history clean from then on. A clone still
downloads every ref its refspec follows, and every blob committed to
`aitask-data` before the move stays in that branch's history.

## 2. Decisions

| # | Topic | Decision |
|---|---|---|
| D1 | Download model | Two layers. (a) `ait setup` / `ait sync` never follow the artifact store branch in routine fetches; a negative refspec excludes it. (b) The `gitbranch` store may live in a **separate artifact repository**, which is the recommended home for large recordings. Per-file external storage (S3 t1089, Drive t1090) remains the future option for single-blob access. |
| D2 | Routing | Route by **size and kind, at creation only**. Binary or over-threshold content goes to a configured `large_backend`. Everything else goes to `default_backend`, as does large content when no `large_backend` is configured (with a warning). With the shipped default (`default_backend` unset, so `local`), small text artifacts therefore stay on the data branch, where they belong to the audit history. A project that sets a non-local `default_backend` keeps that choice for small content too (§4). |
| D3 | Retention | **Nothing expires automatically.** A new explicit `ait artifact prune` is dry-run by default and takes effect only with `--apply`. It always protects the current version, pinned versions and shared blobs. It also protects every version of an artifact that has **any** archived owner, even one shared with an active task, unless `--include-archived` is given. **A pin outlives owner removal:** no command removes a pinned version or deletes its manifest until it is unpinned (§5). |
| D4 | Purge | Only the **artifact store** is compacted, by rebuilding it with live blobs and retiring, then deleting, the old branch. **`aitask-data` history is never rewritten.** Blobs already committed there cannot be reclaimed by the framework. |

**Alternatives rejected:**

- **Automatic keep-last-N.** It silently expires evidence that a plan, a gate
  result or a reviewer may still cite. The cost of keeping text versions is
  negligible, and large data has its own lever (D2 + D4).
- **Rewriting `aitask-data` history** (filter-repo). It destroys the task and
  plan audit history, forces every clone to re-clone or hard-reset, and still
  cannot erase copies held by other clones, forks or backups. If someone needs
  it, it is a manual, out-of-band operation; the framework will not ship it.
- **One default backend for every artifact.** It forces a trade-off between a
  bloated data branch and an external store for small text documents that
  belong in the audit history.
- **Documenting the costs without changing anything.** It leaves `ait sync`
  downloading the entire store history on every machine.

## 3. What a fresh computer downloads

| Step | `local` (data branch) | `gitbranch` on `origin` | `gitbranch` in a separate repo | `dir` | S3 / Drive (future) |
|---|---|---|---|---|---|
| plain `git clone` | the full `aitask-data` history, every blob ever committed | **the full store history** (it is a ref on `origin`) | nothing | nothing | nothing |
| `git clone --single-branch` | code only | code only | nothing | nothing | nothing |
| `ait setup` | fetches `aitask-data` by name, so all of its blobs | nothing | nothing | nothing | nothing |
| `ait sync` | `aitask-data` deltas | **today:** the full store history (`git fetch origin` with no refspec, `aitask_sync.sh:278-284`). **After t2099:** nothing. | nothing (after t2099/t2100) | nothing | nothing |
| first read of one artifact | already local | **the whole store branch**: `ls-remote`, then a full branch fetch (`gitbranch.sh:126-136`) | the whole store branch from that repo | one file | one object |
| a later read of the same version | local | cache hit, no network | cache hit, no network | cache | cache |

### Backend comparison

Rows marked *(future)* describe a backend that is not shipped, and their cells
are design assumptions taken from t1089 / t1090, not measured behaviour. Every
backend shares the per-user blob cache (`~/.cache/ait/artifacts`, §6).

| Backend | New-machine download | Disk use | On-demand access | Offline | Version recovery | Credentials | Operational burden |
|---|---|---|---|---|---|---|---|
| `local` (data branch) | everything ever committed, through `ait setup` | full history in every checkout, permanently (D4) | none needed (already local) | full | every version, plus git history | none beyond repo access | none; the cost is unbounded growth of `aitask-data` |
| `gitbranch`, same repo (`origin`) | plain clone: whole store history. `--single-branch` and `ait setup`: none. `ait sync`: none after t2099 | the main object store holds whatever was fetched; no eviction | first read fetches the whole store branch | cached reads only; writes fail closed (rule R1) until t1259 | every version; the store history also keeps deleted blobs until compaction (t2104) | repo push access | low: branch name config, occasional compaction |
| `gitbranch`, separate repo (t2100) | none | depends on t2100's object-store decision (main repo vs. an isolated bare repo, which would make eviction possible) | first read fetches the whole store branch from that repo | as above | as above | access to a second repo (credential helper / SSH) | medium: a second repository to create, back up and grant access to |
| `dir` | none; the directory must be mounted on each machine | external; the cache holds read copies | one file per read | cached reads work without the mount; uncached reads and writes need it | as long as the directory keeps the blobs; delete really frees space | filesystem / mount access | medium: mount management on every machine (t1968 covers unmount races) |
| S3-compatible *(future, t1089)* | none | external, billed; cache only | one object per read | cached reads only | as long as the bucket keeps the objects (lifecycle rules are the host's) | access keys in env vars or a gitignored file, never in `project_config.yaml` | medium: bucket, keys and cost |
| Google Drive *(future, t1090)* | none | external, quota-bound; cache only | one file per read | cached reads only | as long as Drive keeps the files; delete means trash, then delete | per-user OAuth tokens in a gitignored store | medium-high: OAuth setup and token refresh per user |

### Measured negative-refspec behaviour (t1890 probe, git 2.56.0)

The setup was a scratch bare `origin` with `main`, `aitask-data` and a 2 MB
`aitask-artifacts` store, cloned over `file://`; a plain `/path` clone
hard-links every object and would hide the difference. In the clone,
`git config --add remote.origin.fetch '^refs/heads/aitask-artifacts'` was
added, the store was advanced on `origin`, and then:

| Command | Result |
|---|---|
| `git fetch origin` | store ref absent |
| `git fetch --all --prune` | store ref absent |
| `git fetch origin +refs/heads/aitask-artifacts:refs/remotes/origin/aitask-artifacts` (the gitbranch form) | fetched, `2095c15` |
| `git clone --single-branch -b main` + `git fetch origin aitask-data:refs/remotes/origin/aitask-data` | store blob absent, `size-pack: 1.30 KiB` |
| plain `git clone` (comparison) | store blob present, `size-pack: 1.91 MiB` |

A second named remote `upstream` carried both `main` and `aitask-artifacts` with
the normal mapping `+refs/heads/*:refs/remotes/upstream/*`:

| Configuration | `git fetch --all --prune` |
|---|---|
| normal mapping only | **downloads the store** (`refs/remotes/upstream/aitask-artifacts` created). An exclusion on `origin` alone does not protect a second remote. |
| **shared mode**: keep the positive mapping, add `^refs/heads/aitask-artifacts` | `upstream/main` advanced to a newly pushed code commit; store ref absent |
| **dedicated mode** (store-only remote `ait-store`): `skipFetchAll true`, mapping replaced by `^refs/heads/aitask-artifacts` | remote skipped, no refs. A bare `git fetch ait-store` also fetches nothing. |
| dedicated mode, explicit `git fetch ait-store +refs/heads/aitask-artifacts:…` | works, `2095c15` |
| URL fetch into a private namespace `refs/ait-store/<id>/tip` | works, and `git remote prune` leaves the ref alone |

**Consequences for the design:**

- Exclusion is owned per remote. **Shared mode** (add only the negative refspec,
  keep every positive mapping) is the default for every named remote, `origin`
  included.
- **Dedicated mode** (`skipFetchAll` plus replacing the mapping) applies only to
  a remote explicitly declared as store-only
  (`artifacts.backends.gitbranch.remote_dedicated: true`). Applying it to a
  shared remote would freeze that remote's code branches.
- A store configured as a URL never registers a git remote. It fetches into
  `refs/ait-store/<store_id>/tip`, which no routine fetch or prune touches.
- A plain `git clone` of a repository whose store lives on `origin` always
  downloads the store once. Only `--single-branch`, or putting the store in a
  separate repository, avoids that.

### Partial and shallow fetch: not adopted

- **`--filter=blob:none` plus lazy fetch** requires marking `origin` as a
  promisor remote for the *whole repository*. Every command that touches a
  missing blob would then go to the network, including those on `main`, the
  `aitask-data` worktree and the merge flow, and offline operation would
  degrade repository-wide. That conflicts with the worktree and data-branch
  model.
- **`--depth 1`** on the store branch writes `.git/shallow` grafts that are
  repository-wide state. The CAS write loop also builds every commit on the
  observed tip and must reason about its parents.

Neither is a drop-in fix, so both are deferred and no task is created. D1(b)
plus compaction (§7) bound what a read downloads. Single-blob access is the job
of the per-file backends (t1089, t1090).

## 4. Routing contract (D2)

- **Precedence**, highest first:
  1. an explicit per-call `--backend`;
  2. `large_backend`, when it is set and the content is binary or over the
     threshold;
  3. `default_backend` (unset means `local`, the data branch) for everything
     else, and for large content when `large_backend` is unset. In that case
     the command also prints a warning.
- "Small text stays on the data branch" is the outcome under the shipped
  default, not a separate rule. A project that configured a non-local
  `default_backend` (`dir`, `gitbranch`) deliberately keeps sending small
  content there; routing never overrides a configured default.
- `artifacts.large_backend`: unset by default.
- `artifacts.large_threshold_mb`: default `1`.
- Content counts as **binary** when its first 8 KiB contain a NUL byte, the same
  heuristic git uses.
- **Routing happens at creation only.** A manifest records a single `backend`
  for every version (`artifact_manifest.py` schema), so `update` always keeps
  the artifact's existing backend. When an update's content crosses the
  threshold on a non-large backend, the command warns and names
  `ait artifact move <handle> --to <large_backend>`, which copies every version
  (`aitask_artifact.sh` `move`). Routing only the new bytes would need a backend
  per version, a manifest-model change this design rejects.
- Attachments follow the same routing once they support non-local backends
  (t1258). **Today** `ait attach add` refuses any backend other than `local`.

## 5. Lifecycle states

| State | Entered by | Retained while | Removed by | Automated? |
|---|---|---|---|---|
| **Temporary output** | tool work dirs (`.aitask-screen-recording/`, `.aitask-explain/`, `.aitask-shadow/`), `$TMPDIR` | the tool's own policy | the tool's `clean` verb or by hand | yes (per tool); no evidence guarantee |
| **Promoted evidence** | explicit `ait artifact create` / `update`, `ait attach add` | always (it becomes one of the states below) | only through the states below | — |
| **Current version** | `create` / `update` | the artifact is referenced by any task | `ait artifact rm` of the last reference | no |
| **Historical version** | a newer `update` | indefinitely (D3) | `ait artifact prune --apply` | no; explicit only |
| **Pinned version** | `ait artifact pin` (and artifact-producing gates, t1076_4) | until unpinned, **even after every owner is removed** | nothing, while pinned: `prune` skips it; `rm` of the last reference, hard-delete and the orphaned-manifest reaper keep the manifest (rm and hard-delete refuse unless the user explicitly unpins); compaction counts it as live | no |
| **Archived-task evidence** | archival (which never decrefs) | indefinitely; this covers every version of an artifact with **any** archived owner, including one shared with active tasks | `prune --include-archived --apply`, or `rm` of a loose archived owner | no |
| **Shared blob** | the same hash referenced by >1 manifest version or attachment | any reference remains | never directly; only after it becomes an orphan | — |
| **Expired version** | `prune --apply` | — (the bytes become orphan candidates) | the manifest keeps an `expired` tombstone `{hash, expired_at, by}` | — |
| **Orphan** | no manifest version and no attachment refers to the hash | the grace window | local: `rm` sweep / `ait attach gc` / t1135's reaper. Git store: only by compaction (§7) | yes, after grace (local) |
| **Local cache entry** | any read or write (`~/.cache/ait/artifacts/<hash>`) | the cache budget | cache eviction; always re-fetchable | yes |

- **Reproducibility.** Evidence that a gate result, plan or review cites must be
  **pinned**. An unpinned historical version is reproducible only until someone
  explicitly prunes it.
- **Expired versions.** `ait artifact get --version <hash>` on an expired
  version reports *expired* (with when and by whom) rather than *not found*, so
  a stale citation is visible as such.
- **Archived evidence.** It is never expired by archival alone; that matches the
  t1030_3 attachment decision.

## 6. Cleanup versus permanent purge

| Operation | Frees bytes in | Automatable | Cadence | Dry-run / report | Reference checks | Locking | Failure recovery |
|---|---|---|---|---|---|---|---|
| Reference removal (`artifact rm`, `attach rm`) | nothing yet; it creates orphans | no | on demand | the command output | other tasks' references; the manifest is kept while any reference exists | attach lock | the transaction restores the touched files |
| Version pruning (`artifact prune`) | nothing yet; it creates orphans | no (explicit) | on demand | **default is dry-run** | current, pinned, shared, archived (opt-in) | attach lock | rollback restores the manifest |
| Orphan sweep, local (`rm` sweep, `attach gc`, t1135) | data-branch **tip** only; the history keeps the bytes | yes | on demand / periodic | `attach gc` **today** has none; t2103 adds `--dry-run` | every manifest version plus attachment refs | attach lock | restores from HEAD |
| Orphan handling, `dir` / S3 / Drive | the backend itself (real reclaim) | yes, after grace | periodic | yes | as above | attach lock | per backend; delete is idempotent |
| Orphan handling, `gitbranch` | **nothing**: a delete commit keeps the bytes in history | — | — | — | — | — | handled by compaction instead |
| Cache eviction | `~/.cache/ait/artifacts` | yes | on demand / size cap | yes | never evicts a local-backend symlink target | none needed (re-fetchable) | re-fetch |
| Store compaction (`gitbranch`) | the store, after `--delete-retired` and the remote's own gc | no (explicit) | rare | **preview by default** | §7 contract | attach lock + CAS fence | the retired branch and a backup ref stay until deletion |
| Git-history removal on `aitask-data` | — | **not provided** | — | — | — | — | — |

**`git gc` does not erase blobs.** A blob deleted in a new commit is still
reachable from the older commits that contain it, so `git rm` followed by
`git gc` reclaims nothing. Only a blob that no ref, reflog or stash can reach is
pruned. That is why a data-branch orphan sweep cleans the working tip and never
shrinks a clone.

## 7. Compaction safety contract

Compaction (t2104) rebuilds the store branch with only the live blobs. The live
set seen in one checkout **does not prove** that a blob is garbage.
`create` / `update` publish the blob to the store (`aitask_artifact.sh:429`,
`:547`) before the manifest is committed, and the data branch is pushed
separately. Another clone can therefore hold a published blob whose manifest the
compacting clone cannot see yet (t1231_4 observed the same gap from the reading
side).

Compaction is allowed only under all five rules:

1. **Fresh references.** Fetch `aitask-data` first and refuse unless the local
   data branch equals the remote tip.
2. **Age-based eligibility.** A blob may be excluded only if the store commit
   that added it is older than `artifacts_compaction_grace` (default `30d`).
   Within the grace window it is carried forward, whether or not it is
   referenced.
3. **Non-destructive first step.** The new store goes on a new branch. The old
   branch is retired with the existing `gitbranch-migrate` fence
   (`.ait-artifact-retired`), stays readable, and serves as the read fallback
   when a version is missing from the compacted store.
4. **Late-reference sweep before deletion.** `--delete-retired` is a separate,
   explicit step, allowed only after the grace window. It re-fetches
   `aitask-data`, copies forward every blob that a now-visible manifest or
   attachment references, and only then deletes the retired branch on the
   remote.
5. **One retirement at a time.** A new compaction is refused while a retired
   predecessor still exists. The fallback is therefore always one level deep,
   and an excluded blob can never be stranded two generations back. The refusal
   names the pending branch and the earliest time `--delete-retired` is allowed.

Compaction also refuses while the local store is ahead of the remote, which
means unpublished writes; it coordinates with t1259's offline queue.

**Coordination requirement (stated in the user docs).** A clone that keeps
manifest commits unpushed for longer than the grace window, across a
`--delete-retired`, can lose those bytes. The deletion step prints this
requirement and the number of blobs it is about to make unreachable.

## 8. Migration and existing history

- **Copying and repointing are not reclaiming.** `ait artifact move` copies
  every version and repoints the manifest; the source blobs remain.
  `gitbranch-migrate` copies a store to a new branch and fences the old one,
  which stays readable. Neither removes a single object from any history.
- **Existing data-branch blobs.** After switching `default_backend` or
  configuring `large_backend`, new artifacts go to the new store. Existing ones
  move only through an explicit `move`, and their bytes stay in `aitask-data`
  history permanently (D4).
- **Moving a store between remotes** (`origin` to a separate repo) is a
  `gitbranch-migrate` extension (t2100). After migration and a later
  `--delete-retired`-style removal of the `origin` branch, new clones of the
  code repository no longer download it.
- **Old clones resynchronize** through the store record on `aitask-data`
  (`artifacts/gitbranch_store.json`) and the retired marker: a stale clone's
  next operation refuses and names the migration, or follows the fallback,
  rather than writing to the old store. Their local copies of the old objects
  stay until their own `git gc` and reflog expiry.
- **Remote-host constraints.** Deleting a branch on a hosted remote makes its
  objects unreachable, but the host decides when to garbage-collect them. Forks,
  caches and pull-request refs may keep them indefinitely, and some hosts purge
  only on a support request.
- **Purge scope.** No command run in one checkout can erase copies in other
  clones, forks, CI caches or backups. The strongest guarantee the framework
  gives is that, after compaction and `--delete-retired`, **new** clones and
  routine fetches no longer download the bytes and the configured remote no
  longer references them. It is not erasure.

## 9. High-volume and screen-recording evidence

One disposable-data policy does not fit every kind:

| Kind | Policy |
|---|---|
| Original recordings | transient by default (t1165); never copied into the repo. Keeping them is an explicit opt-in that goes to a **separate artifact repository** (D1b), never to `aitask-data`. |
| Extracted frames, contact sheets, generated HTML from the screen-recording skill | temporary output in the gitignored `.aitask-screen-recording/` work dir with a `clean` verb (t1888's E7 decision, delivered by t1893_11) |
| Selected evidence the user chooses to keep | promoted only through explicit `ait artifact create` / `update`; routing (D2) sends binaries to `large_backend` |
| Small durable documents (implementation trails, HTML plans) | data branch; every version kept (D3); cheap and part of the audit history |

## 10. Task map

| Concern | Task |
|---|---|
| Routine-fetch exclusion for every store remote (shared and dedicated mode) | t2099 |
| `gitbranch` in a separate artifact repository | t2100 (depends on t2099) |
| Size/kind routing at creation | t2101 |
| Manifest lifecycle on hard delete, orphaned-manifest reaper | t1135 (existing) |
| Pin, explicit prune, expiry tombstones | t2102 (depends on t1135) |
| `gitbranch` store compaction (§7) | t2104 (depends on t2102) |
| `attach gc --dry-run`, cache eviction, usage report | t2103 |
| Website storage-lifecycle concept page | t2105 (depends on t2099–t2102, t2104) |
| Attachments on non-local backends (routing and retention apply) | t1258 (existing) |
| Offline `gitbranch` write queue (compaction refuses while pending) | t1259 (existing) |
| Per-file external storage | t1089 S3, t1090 Drive (existing) |
| Gate-produced evidence pinned | t1076_4 (existing) |
| Screen-recording work dir | t1893_11 (existing) |

Verification scenarios, each owned by the task listed:

| Scenario | Task |
|---|---|
| fresh-clone transfer cost | t2099, t2100 |
| combined t2099 + t2100, and mixed code-and-artifact remote | t2099, t2100 |
| shared-blob retention, archived/pinned evidence, version expiry and tombstone | t2102 |
| threshold-crossing update | t2101 |
| offline cached retrieval | t2100 |
| concurrent cleanup and write | t2102, t2104 |
| two-clone withheld manifest, two compactions with a cold cache | t2104 |
| migration between remotes | t2100 |
| old-clone resynchronization | t2104 |
