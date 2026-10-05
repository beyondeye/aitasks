---
priority: medium
effort: medium
depends: []
issue_type: chore
status: Ready
labels: [task_attachments]
gates: [risk_evaluated]
anchor: 1065
created_at: 2026-10-05 14:36
updated_at: 2026-10-05 14:36
---

## Goal

Review and finalize the storage lifecycle for task artifacts, including their
shared blob store with attachments. Agree with the user on a design that keeps
task history useful without making every new checkout download an ever-growing
collection of recordings, generated frames, and obsolete artifact versions.

Deliver a durable design decision and scoped implementation tasks. This is a
design/review task; do not perform history rewriting, destructive purging, or
implement every backend as part of it.

## Research already done

These findings were checked in the repository on 2026-10-05 while helping the
user answer t1888's E7 storage question. Revalidate them against the current tree
and task status before relying on them:

- The default `local` backend puts artifact AND attachment blobs in the data
  worktree at `attachments/blobs/<2>/<62>` and commits them to `aitask-data` in
  branch mode. Artifact manifests retain every recorded version. The only
  other shipped adapter found was `dir`, an external mounted directory.
- `ait artifact rm` removes a task reference and, on the last reference, the
  manifest and eligible local blobs. Deletions are ordinary Git commits, so
  the old bytes remain recoverable from data-branch history. Non-local blob
  deletion is not currently handled by this command.
- `ait artifact move` copies every version, verifies it, and repoints the
  manifest. Source blobs remain; moving does not purge old Git history.
- `ait attach gc` is opt-in and sweeps fully orphaned attachment blobs after
  `attachments_gc_grace` (default 30d). Active AND archived task references,
  and every artifact-manifest version, protect blobs. Archiving a task does
  not expire its evidence. No automatic artifact version-retention policy or
  complete Git-history purge workflow was found.
- Pending t1231 / t1231_1 introduce a dedicated orphan Git branch (default
  `aitask-artifacts`). That separates future blob history from task history,
  but an ordinary clone still fetches all branches. The proposed backend
  fetches the artifact branch on use, rather than downloading only one
  requested blob. Moving storage also leaves previously committed blobs in
  `aitask-data` history.
- Pending t1135 covers artifact manifest lifecycle on task deletion and orphan
  reaping; this is distinct from removing bytes from Git history. Pending
  t1258 extends attachments to non-local backends; t1259 covers offline writes
  to the branch backend. Pending t1089/t1090 cover S3-compatible/Google Drive
  storage.

Git references supporting the distinctions above:

- https://git-scm.com/docs/git-clone — default branch fetching, single-branch,
  shallow and partial-clone options.
- https://git-scm.com/docs/git-gc — reachable history is retained.
- https://git-scm.com/docs/git-filter-branch#_checklist_for_shrinking_a_repository
  — removing files from reachable history and reclaiming objects are separate
  steps. This is background documentation, not a recommendation to implement
  purging with `filter-branch`.

## Review and decisions

1. **Storage and download model.** Compare the existing data-branch backend,
   a dedicated branch in the same repository, a separate artifact repository,
   and external blob storage (`dir`, S3-compatible, Drive). For each, explain
   new-machine download cost, disk use, on-demand access, offline behavior,
   version recovery, credentials, and operational burden. Distinguish a clean
   task-data branch from a small clone. If choosing a Git branch, specify how
   initial clone, task initialization, background sync, and artifact retrieval
   avoid unintentionally fetching the full blob history. Partial/shallow fetch
   approaches need compatibility analysis against the backend's write and
   concurrency model; do not assume they are drop-in fixes.
2. **Retention policy.** Define lifecycle states and transitions for temporary
   output, explicitly promoted evidence, current and historical versions,
   archived-task evidence, shared blobs, and orphans. Decide defaults, pinning,
   age/version/size limits, and what requires a user's explicit deletion
   choice. Define which evidence must remain reproducible and what happens
   when a historical version is deliberately expired. Apply the policy to
   attachments as well as artifacts where they share storage.
3. **Cleanup versus permanent purge.** Separate reference removal, version
   pruning, orphan sweeping, local cache eviction, backend deletion, and Git
   history removal. Specify which operations can be automated, their cadence,
   dry-run/report behavior, reference checks, locking, and failure recovery.
   Ordinary Git deletion plus `git gc` must not be presented as a way to erase
   blobs that old commits still reference. Evaluate dedicated artifact-branch
   compaction versus keeping binary bytes outside Git; preserve the task/plan
   audit history where possible.
4. **Migration and existing history.** Explain what happens to existing local
   artifacts and shared attachments when changing backends. Distinguish
   copying/repointing live data from reclaiming historic Git objects. If
   history rewriting or branch compaction is chosen, define preview, backup,
   coordination with concurrent sessions, remote-host reclamation constraints,
   and how existing clones resynchronize. State that one checkout cannot erase
   copies in other clones or backups; define the actual scope of any purge
   guarantee. No destructive migration runs during this review.
5. **High-volume screen-recording use case.** Coordinate the proposed policy
   with t1888/E7: originals and bulk extracted frames should have an explicit
   temporary-versus-durable decision, with selected evidence promoted only
   through a clear user-facing flow. Treat this as a recommendation to agree
   with the user, not a silently imposed change to t1888. Include generated
   HTML/contact sheets and small durable documents such as implementation
   trails; do not apply one disposable-data policy to all artifact kinds.
6. **Finalize and sequence.** Discuss material tradeoffs with the user and
   record the chosen policy, alternatives and rationale in the artifact design
   docs. Review overlaps with t1231, t1135, t1258, t1259, t1089, t1090 and t1888
   before creating work. Create only missing implementation tasks, grouped in
   the artifact-storage topic with clear dependencies, acceptance criteria,
   verification ideas, and website documentation deliverables. Use advisory
   notes to convey decisions to existing tasks rather than duplicating them.

## Reference files

- `aidocs/unified_artifact_design.md`
- `aidocs/task_attachments_design.md`
- `.aitask-scripts/aitask_artifact.sh`
- `.aitask-scripts/aitask_attach.sh`
- `.aitask-scripts/lib/artifact_backends/local.sh`
- `.aitask-scripts/lib/artifact_backends/dir.sh`
- `.aitask-scripts/lib/artifact_cache.sh`
- `.aitask-scripts/lib/artifact_manifest.py`
- `.aitask-scripts/lib/artifact_registry.py`
- `.aitask-scripts/aitask_init_data.sh`
- `.aitask-scripts/aitask_sync.sh` and `aitask_syncer.sh`
- `aiplans/p1231_configurable_git_branch_artifact_backend.md` (resolve its
  current location if archived)
- `aidocs/screen_recording_skill_design_review.md`, E7

## Done when

- The user has agreed on the storage/download strategy and retention policy,
  and the decisions are recorded in the design docs with a lifecycle table.
- The design answers both questions separately: "what does a fresh computer
  download?" and "how do we reclaim storage for evidence we no longer need?"
- Current cleanup limitations, migration of existing history, purge scope, and
  protections for retained/shared evidence are explicit.
- Implementation work is mapped to existing or newly created tasks without
  duplication, including documentation and meaningful verification scenarios:
  fresh-clone transfer cost, shared-blob retention, archived/pinned evidence,
  version expiry, offline retrieval, concurrent cleanup/write, migration, and
  old-clone resynchronization where applicable.
