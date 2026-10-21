---
Task: t1890_review_finalize_artifact_storage_lifecycle.md
Base branch: main
Output branch: main
plan_verified: []
---

# t1890 — Review & finalize artifact storage lifecycle

## Context

Artifacts and attachments share a content-addressed blob store. Today, blobs on
the default `local` backend are committed to `aitask-data`, so every checkout
downloads them. The shipped `gitbranch` backend (t1231, archived) moves new
blobs to an orphan branch on `origin`. But a plain `git clone`, `ait sync`
(`git fetch origin` with no refspec, `aitask_sync.sh:278-284`) and
`fetch --all` (`aitask_web_merge.sh:240`) all download that branch's full
history. Reading one artifact fetches the whole branch (`gitbranch.sh:126-136`).

Several things are missing:
- Manifests are append-only and nothing prunes versions
  (`artifact_manifest.py:215-219`).
- `attach gc` never reclaims artifact-only blobs, has no dry-run, and sweeps
  local blobs only (`aitask_attach.sh:642, 690-692, 735`).
- `rm` leaves `dir` and `gitbranch` blobs in place (`aitask_artifact.sh:894-896`).
- `gitbranch` delete only adds a commit, so the bytes stay in branch history.
- The `~/.cache/ait/artifacts` cache is never evicted.

This design/review task records the agreed lifecycle policy in the design docs
and maps the implementation work to tasks without duplicating existing ones. It
does no destructive operation and no history rewrite.

### Decisions agreed with the user (2026-10-21)

1. **Download model:** two layers.
   - Normal `ait setup` / `ait sync` skip artifact history through a negative
     fetch refspec.
   - Support a **separate artifact repository** (a `gitbranch` remote other than
     `origin`), recommended for large recordings.
   - Document honestly that a plain clone still fetches the artifact branch while
     it lives on `origin`, and that reading one artifact may fetch the whole
     artifact branch.
   - Per-file external storage (t1089 S3, t1090 Drive) stays the future option.
2. **Routing:** tier by size and kind. Small text artifacts stay on the data
   branch. Binary or over-threshold blobs go to a configured `large_backend`.
   When none is configured, the command warns and stores locally.
3. **Retention:** nothing expires automatically. A new explicit
   `ait artifact prune` is dry-run by default and applies only with `--apply`.
   It protects the current and pinned versions, shared blobs, and archived-task
   evidence (unless explicitly included).
4. **Purge:** only the artifact store is compacted: rebuild it with live blobs
   only, then retire and delete the old branch. `aitask-data` history is never
   rewritten, and blobs already committed there are documented as
   non-reclaimable by the framework.

Already settled elsewhere and recorded only:
- t1888/E7: screen-recording outputs go to the gitignored
  `.aitask-screen-recording/` work dir (t1893_11), not to the store.
- t1165: original recordings are transient by default.

## Implementation

### Pre-phase (risk mitigations)

1. [probe_negative_refspec] Build the scratch setup in the session scratchpad:
   - a bare origin holding `main`, `aitask-data` and `aitask-artifacts`;
   - a clone of it with `git config --add remote.origin.fetch '^refs/heads/aitask-artifacts'`.

   In that clone, confirm all three of the following:
   - `git fetch origin` does not create or update `refs/remotes/origin/aitask-artifacts`.
   - `git fetch --all --prune` does not create or update it either.
   - The gitbranch-style explicit fetch
     `git fetch -q origin +refs/heads/aitask-artifacts:refs/remotes/origin/aitask-artifacts`
     still fetches it.

   Also check that `git clone --single-branch -b main`, followed by fetching
   `aitask-data` by name, leaves no store objects (`git count-objects -v`).

   Then add a second bare repo `upstream` that carries **both** `main` and
   `aitask-artifacts`, as a named remote with a normal fetch mapping. Confirm
   that `git fetch --all --prune` downloads the store branch (this reproduces
   the reviewer's finding).

   **Shared mode.** Keep the positive mapping, add only
   `^refs/heads/aitask-artifacts`, and push a new commit to `upstream`'s `main`.
   Confirm that `fetch --all --prune` advances `upstream/main` and does not
   fetch the store.

   **Dedicated mode.** On a store-only remote, set `skipFetchAll` and replace
   the mapping. Confirm the remote is skipped, while an explicit-refspec fetch,
   either from the remote or from its URL into `refs/ait-store/<id>/tip`, still
   works.

   Record the commands and results verbatim in the design doc's download-model
   section, so the evidence lasts. If a result contradicts the assumption,
   rewrite task A's description to match what was observed before creating it.

### 1. New design record `aidocs/artifact_storage_lifecycle.md`

The record contains these sections:

- **Two questions, answered separately.**
  - (a) *What does a fresh computer download?* A per-backend table covering
    clone, `ait setup`, `ait sync` and first read: current vs. after tasks A/B.
  - (b) *How do we reclaim storage?* Points to the cleanup-vs-purge table.
- **Backend comparison.** One row per option: `local` data branch, same-repo
  `gitbranch`, separate-repo `gitbranch`, `dir`, S3 (t1089), Drive (t1090).
  Columns: new-machine download, disk use, on-demand access, offline behaviour,
  version recovery, credentials, operational burden. The text distinguishes "a
  clean task-data branch" from "a small clone".
- **Partial and shallow fetch analysis.**
  - `--filter=blob:none` with a promisor remote changes `origin` for the whole
    repo, which the worktree and data-branch model does not tolerate.
  - `--depth 1` writes repo-wide `.git/shallow` grafts, and the CAS parent
    chain needs the observed tip.
  - Both are deferred, with no task. Compaction plus a separate repo bound the
    history instead.
- **Lifecycle table.** Columns: state → how it is entered, how it is retained,
  what may remove it, and whether removal is automated or needs an explicit
  user choice. States:
  - temporary output (work dirs and `$TMPDIR`; `clean` verbs; no evidence
    guarantee);
  - promoted evidence (`ait artifact create/update`, `ait attach add`);
  - current version;
  - historical version;
  - pinned version;
  - archived-task evidence;
  - shared blob;
  - orphan;
  - local cache entry;
  - expired version.

  An expired version keeps a manifest tombstone `{hash, expired_at, by}`, so
  `get --version` reports "expired" rather than "not found". Evidence that a
  gate result or plan references must be pinned to stay reproducible.
- **Defaults and routing contract.**
  - `large_threshold_mb: 1`.
  - Binary heuristic: a NUL byte in the first 8 KiB.
  - The per-call `--backend` override takes precedence.
  - **Routing happens at creation only.** A manifest has a single `backend` for
    every version (`artifact_manifest.py` schema), so `update` always keeps the
    artifact's existing backend. When an update crosses the threshold on a
    non-large backend, it warns and names `ait artifact move <handle> --to
    <large_backend>`, which copies every version. Routing only the new bytes
    would need per-version backends, a manifest-model change that is rejected
    here.
  - Routing applies to attachments through t1258.
- **Compaction safety contract (unsynchronized references).**
  - `create` / `update` publish the blob to the store
    (`aitask_artifact.sh:429/547`) before the manifest is committed, and the
    data branch is pushed separately. So another clone can hold a published
    blob whose manifest the compacting clone cannot see yet.
  - The live set computed in one checkout is therefore never proof that a blob
    is garbage. Compaction is safe only under all of these rules:
    1. **Fresh references.** Fetch `aitask-data` from the remote first and
       refuse unless the local data branch equals the remote tip, so every
       published manifest is counted.
    2. **Age-based eligibility.** A blob is eligible for exclusion only if the
       store commit that added it is older than `artifacts_compaction_grace`
       (default `30d`). A blob published within the grace period is always
       carried forward, referenced or not.
    3. **Non-destructive first step.** Compaction writes a new branch and
       retires the old one with the existing migrate fence, which stays
       readable. Reads that miss in the compacted store fall back to its
       retired predecessor while the predecessor exists.
    4. **Late-reference sweep before deletion.** Deleting the retired
       predecessor is a separate explicit step (`--delete-retired`), allowed
       only after the grace period. It re-fetches `aitask-data` and copies
       forward any blob that a now-visible manifest or attachment meta
       references, then deletes.
    5. **One retirement at a time.** A new compaction is refused while a
       retired predecessor from an earlier compaction still exists, meaning
       `--delete-retired` has not resolved it yet. The read fallback is
       therefore always exactly one level deep, and a blob excluded by the
       previous compaction can never be stranded in an older ancestor that the
       current store does not fall back to. The refusal message names the
       pending retired branch and the earliest time `--delete-retired` is
       allowed.
  - **Explicit coordination requirement**, stated in the docs: a clone that
    keeps manifest commits unpushed for longer than the grace period, across a
    `--delete-retired`, can lose those bytes. The deletion step prints this
    requirement and the count of blobs it is about to make unreachable.
- **Cleanup vs. permanent purge table.** One row per operation: reference
  removal, version pruning, orphan sweep, cache eviction, backend deletion,
  store compaction, and Git-history removal. Columns: automatable?, cadence,
  dry-run/report, reference checks, locking, failure recovery. It states
  explicitly that ordinary Git deletion plus `git gc` does **not** erase blobs
  that old commits still reference.
- **Migration and existing history.**
  - Copy/repoint (`move`, `gitbranch-migrate`) is distinguished from reclaiming
    old objects.
  - Covers preview, backup ref, the fence for concurrent clones, how old clones
    resynchronize, and remote-host constraints (hosted services may keep
    unreachable objects; no timely erasure).
  - Purge-scope statement: one checkout cannot erase copies held by other
    clones, forks or backups.
- **Screen-recording / high-volume policy.** Per-kind policy:
  - originals: transient, or a separate artifact repo with explicit opt-in;
  - extracted frames and contact sheets: temporary work dir;
  - promoted evidence: explicit `ait artifact create` only;
  - small durable docs (trails, HTML plans): data branch, keep all versions.

  One disposable-data policy is not applied to all kinds.
- **Alternatives rejected, with rationale:**
  - automatic keep-last-N;
  - rewriting `aitask-data` history;
  - a single backend for all artifacts;
  - docs-only.
- **Task map.** Existing tasks plus the new tasks A–G below, each with its
  verification scenario.

### 2. Cross-references in existing design docs

- `aidocs/unified_artifact_design.md` §9 (Lifecycle, ~L411):
  - add a short paragraph pointing to the new doc;
  - reword "until that version is itself pruned" to name the explicit-prune
    policy;
  - add a §14 cross-ref entry.
- `aidocs/task_attachments_design.md` §8 (Lifecycle) and §12: one-line pointer
  each, and a note that routing and retention apply to attachments through
  t1258.

### 3. Website: describe what is downloaded today

`website/content/docs/commands/artifact.md`, section "The gitbranch backend":
add a short "What gets downloaded" paragraph, written in the current state only:
- A plain `git clone` fetches the store branch while it lives on `origin`.
- `ait sync` also fetches it today.
- Reading an artifact that is not cached fetches the whole store branch.
- `git clone --single-branch` avoids the first download.

Task A updates the `ait sync` sentence when it lands. Then run
`cd website && python3 check_links.py --build`.

### 4. Create the implementation tasks

Use `aitask_create.sh --batch --commit`. Settings for every task: label
`task_attachments`, `--anchor 1065`, priority medium unless noted. Each
description carries: context, key files, acceptance criteria, verification
scenarios, and its own website/doc updates.

- **A — `artifact_fetch_exclusion`** (feature).
  - `ait setup` / `aitask_init_data.sh` add a negative refspec
    `^refs/heads/<store branch>` to `remote.origin.fetch` (git ≥ 2.29;
    otherwise warn).
  - Settings branch change and `gitbranch-migrate` keep it in sync.
  - Verify that `ait sync` and web-merge `fetch --all` skip the branch, and that
    gitbranch's explicit-refspec fetch still works.
  - Owns **routine-fetch exclusion for every remote the store uses**, not only
    `origin`. There are two modes.
    - **Shared remote** (the default for any named remote, `origin` included):
      keep every existing positive `remote.<name>.fetch` mapping and only *add*
      `^refs/heads/<store>`. Code branches on that remote, such as
      `upstream/main`, keep updating.
    - **Dedicated remote**: only when explicitly declared
      (`artifacts.backends.gitbranch.remote_dedicated: true`). Setup also sets
      `remote.<name>.skipFetchAll true` and replaces the remote's mapping with
      the negative refspec.
    - Mapping replacement is never applied to a remote that is not declared
      dedicated.
    - gitbranch's own explicit-refspec fetch keeps working in both modes.
  - Tests:
    - a scratch origin with a store branch, then a fresh clone with
      `--single-branch` plus setup and sync must leave
      `refs/remotes/origin/<store>` absent;
    - an old clone after enabling the exclusion;
    - **combined A+B**: once a separate named store remote is configured,
      `git fetch --all --prune` and `ait sync` create no store refs and fetch
      no store objects (`git count-objects -v` unchanged), while
      `ait artifact get` still works;
    - **mixed code-and-artifact remote**: a shared named remote carries both
      `main` and the store branch. Push a new commit to its `main`, then run
      `fetch --all --prune`. Assert that `<remote>/main` advanced to the new
      commit while no store ref or store objects were fetched;
    - **dedicated mode**: `skipFetchAll` is set only when declared.
  - Docs: `commands/artifact.md`, `concepts/git-branching-model.md`.
- **B — `gitbranch_separate_remote`** (feature; depends on **A**).
  - New `artifacts.backends.gitbranch.remote` (a remote name or URL; default
    `origin`), validated by the registry.
  - Every ls-remote, fetch and push in `gitbranch.sh` uses it.
  - **URLs do not register a git remote.** A URL value is fetched directly with
    an explicit refspec into a private namespace (`refs/ait-store/<store_id>/tip`).
    That namespace lies outside `refs/remotes/`, so `fetch --all` and
    `remote prune` never see it.
  - **Named remotes.** A named-remote value is accepted, and A's exclusion
    applies to it. The default is shared mode: the store-branch negative
    refspec is added and existing mappings are preserved. Dedicated mode
    (`skipFetchAll` plus mapping replacement) applies only with
    `remote_dedicated: true`. B adds that key to the registry and the settings
    tab. B depends on A for this reason, and B's tests repeat the combined A+B
    check and the mixed-remote check.
  - The store record gains `remote`; the settings tab gets the field.
  - `gitbranch-migrate` can move a store between remotes.
  - Decide and document where fetched objects live (main object store vs. an
    isolated bare repo).
  - Covers credentials, and offline reads from cache.
  - Tests: migration from `origin` to a separate remote; a fresh clone
    downloads no blob bytes; offline cached read.
  - Docs: recommended setup for large recordings.
- **C — `artifact_size_kind_routing`** (feature).
  - New keys `artifacts.large_backend` and `artifacts.large_threshold_mb`
    (default 1).
  - **Routing at creation only.** `create` routes binary or over-threshold
    content to `large_backend`.
  - `update` keeps the artifact's existing backend, because a manifest has one
    backend for all versions. When an update crosses the threshold it warns and
    names `ait artifact move --to <large_backend>`. Nothing moves automatically.
  - Warns when `large_backend` is unset.
  - Tests:
    - routing;
    - override precedence;
    - the unset warning;
    - a **threshold-crossing update**: create a small artifact on `local`, then
      update it with over-threshold content. Assert that the backend is
      unchanged, the warning is printed, and both the current and the
      historical version are retrievable. Then run `move` and assert both
      versions are still retrievable.
  - Docs: config tables plus a seed comment.
- **D — `artifact_pin_and_prune`** (feature; depends on **t1135**).
  - Manifest `pinned` list and `expired` tombstones (schema extension; follow
    `aitasks_extension_points.md`).
  - New verbs `ait artifact pin/unpin`, and
    `prune <handle>|--all [--keep N] [--older-than DUR] [--include-archived] [--apply]`
    (dry-run report by default).
  - Protects current, pinned and shared hashes (other manifests plus attachment
    metas). Runs under the attach lock with rollback, and sweeps local blobs
    through t1135's sweep. Non-local orphans are left for E.
  - Tests: shared-blob retention, archived/pinned evidence, version expiry and
    tombstone `get`, concurrent prune vs. update.
- **E — `gitbranch_store_compaction`** (feature; depends on **D**).
  - Implements the **compaction safety contract** from the design doc:
    1. Fresh-reference precondition: fetch `aitask-data` and refuse unless the
       local data branch equals the remote tip.
    2. The live set comes from all manifests and attachment metas at that tip.
    3. Age-based eligibility: blobs published within
       `artifacts_compaction_grace` (default `30d`) are always carried forward.
    4. Preview of counts and bytes; a backup ref.
    5. A rebuilt fresh-root store on a new branch, reusing the migrate copy +
       fence machinery. The old branch is retired, stays readable, and serves
       as the read fallback.
    6. A separate `--delete-retired` step, allowed only after the grace period,
       that first runs the late-reference sweep (re-fetch `aitask-data`, copy
       forward any newly referenced blobs) and prints the coordination
       requirement.
  - Refuses while a retired predecessor from an earlier compaction still
    exists (one retirement at a time).
  - Also refuses when the local store is ahead of the remote (unpublished
    writes; coordinate with t1259).
  - Tests:
    - **Two-clone withheld manifest.** Clone Y publishes a blob and withholds
      its manifest commit through compaction in clone X. With the blob inside
      the grace period, it is carried forward. With the grace forced to `0`,
      the blob is excluded, but Y's `get` succeeds via the retired fallback
      after Y pushes the manifest, and `--delete-retired` copies the blob
      forward rather than losing it.
    - **Two compactions, delayed manifest, cold cache.**
      1. Y publishes a blob and withholds its manifest.
      2. X compacts store A into B with the grace period set to `0`, so the
         blob is excluded from B.
      3. X attempts a second compaction (B to C). It is refused, naming the
         pending retired branch A.
      4. Y pushes the manifest.
      5. X clears `~/.cache/ait/artifacts` and runs `get`. It succeeds through
         the fallback to A.
      6. `--delete-retired` copies the blob forward into B and deletes A.
      7. The second compaction (B to C) now runs. A cold-cache `get` succeeds
         from C.
    - A concurrent write during compaction loses nothing.
    - An old clone resynchronizes.
    - A dry run makes no changes.
  - Docs state the purge scope and the coordination requirement.
- **F — `storage_cleanup_reporting`** (enhancement, low effort).
  - `ait attach gc --dry-run`.
  - `ait artifact cache prune [--older-than] [--max-size]`, which never removes
    the local-backend symlink targets.
  - `ait artifact usage`: bytes per backend and kind, and what a fresh clone
    would download.
  - Tests per verb.
- **G — `website_storage_lifecycle_page`** (documentation; depends on A–E).
  - A `concepts/` page on the storage lifecycle (download model, tiers,
    retention, purge scope).
  - Links from `concepts/artifacts.md` and `concepts/attachments.md`.
  - Run `check_links.py`.

After creating them, fill the real IDs into the task map in
`aidocs/artifact_storage_lifecycle.md`.

### 5. Advisory notes to existing tasks (`ait note … --from 1890`)

| Task | Note |
|---|---|
| t1135 | D depends on its sweep. Non-local orphan reaping for `gitbranch` should defer to compaction (E) instead of per-blob delete commits, which reclaim nothing. Any non-local reaping must respect the unsynchronized-reference contract: a blob published before its manifest is pushed is not an orphan. Add `--dry-run` parity with F. |
| t1258 | Apply C's size/kind routing and D's retention to attachments on non-local backends. |
| t1259 | E refuses to compact while queued, unpublished writes exist, so the pending-state check must be queryable. |
| t1089, t1090 | Recorded as the future per-file external option. Real backend delete is where reclaim actually happens. |
| t1165 | Large originals: separate artifact repo (B) with explicit opt-in. Policy cross-ref. |
| t1076_4 | Artifacts produced by gates should pin the evidence version (D) so it stays reproducible. |
| t1134 | The lifecycle policy applies to both attachments and artifacts. Cross-ref the doc. |

### 6. Commit

- The doc changes (`aidocs/`, `website/`) go in one code commit:
  `chore: Record artifact storage lifecycle decisions (t1890)`.
- The plan goes through `aitask_task_commit.sh`.

Step 9 then handles archival. The `risk_evaluated` gate is recorded by the
orchestrator.

## Verification

- `cd website && python3 check_links.py --build`, plus `hugo build --gc --minify`.
- `bash tests/test_website_doc_lists.sh`, the backend-table drift guard.
- The new aidoc's cross-refs resolve (grep the paths).
- Each created task file exists with `anchor: 1065` and the right `depends:`
  (`./.aitask-scripts/aitask_ls.sh -v 99 | grep -E 'fetch_exclusion|separate_remote|…'`).
- Every `ait note` returns `NOTE_APPENDED:`.

## Risk

### Code-health risk: low
None identified. The task changes only docs, creates tasks and sends notes; it
changes no code.

### Goal-achievement risk: low
- The recommended download model (task A) rests on the untested assumption that
  a negative `remote.origin.fetch` refspec makes `ait sync`/`fetch --all` skip
  the store branch while gitbranch's explicit-refspec fetch keeps working.
  Severity: low (residual; addressed by inline pre-phase probe_negative_refspec).
  → mitigation: inline pre-phase probe_negative_refspec
- The compaction (E) and routing (C) contracts could encode unsafe or
  incoherent behaviour. Examples: a live set that misses another clone's unpushed
  manifest, and a threshold crossing on update with a single-backend manifest.
  Severity: low (residual; addressed in this plan by the compaction safety
  contract, update-keeps-backend routing, and the required two-clone and
  threshold-crossing tests in E/C). → mitigation: none (addressed in design).
- Routine fetches could still download the store through a separate named
  remote (A+B). Severity: low (residual; A owns exclusion for every store
  remote; combined A+B test; extended probe). → mitigation: inline pre-phase
  probe_negative_refspec
- New tasks could duplicate existing scope (t1135/t1258/t1259/t1089/t1090).
  Severity: low. → mitigation: none (dependency edges plus advisory notes in
  step 5).

### Planned mitigations
- timing: pre-phase | name: probe_negative_refspec | type: chore | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: unverified negative-refspec assumption behind task A | desc: probe fetch/fetch --all/explicit-refspec behaviour with a negative refspec in a scratch repo and record results in the design doc
