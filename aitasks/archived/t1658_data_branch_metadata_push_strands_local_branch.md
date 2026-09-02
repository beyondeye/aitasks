---
priority: high
effort: medium
depends: []
issue_type: bug
status: Done
labels: [git, bash_scripts, task_metadata, robustness]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
created_at: 2026-09-01 09:25
updated_at: 2026-09-02 19:01
completed_at: 2026-09-02 19:01
---

## Symptom

`ait syncer` persistently reports `aitask-data` as behind origin, listing
"remote commits not yet pulled" that in fact **originated from this machine**
(`ait: Update verified score …`, `ait: Update usage count …`). The same
divergence makes the task-workflow's encapsulated data-branch operations fail
with non-fast-forward errors. Nothing converges automatically — only an
explicit sync from `ait syncer` clears it, and it comes back.

## Root cause

Four defects compound. All were reproduced on a live repo.

### 1. The generator pushes off-branch

`.aitask-scripts/lib/verified_update_lib.sh:113` `commit_and_push_from_remote_clone()`
builds every metadata commit in a **throwaway `/tmp` clone** of
`origin/<data-branch>`, then pushes `HEAD:<branch>` straight to origin. The
local branch ref is never advanced, so the commit can only reach this
repository through a *later* fetch. This is the framework's only temp-clone
push site, and it fires **twice per completed pick** via
`satisfaction-feedback.md` (`aitask_usage_update.sh`, then
`aitask_verified_update.sh`). Those two subjects are ~15% of recent
data-branch commits (61 of the last 400).

### 2. The compensating sync refuses before it fetches

The function's only compensation is `sync_current_repo_from_remote()` →
`task_sync()` immediately after the push. `_task_pull_rebase()`
(`lib/task_utils.sh:478`) is a bare `pull --rebase --quiet` with **no
`--autostash`**, and `rebase.autoStash` is not configured. Git therefore
refuses outright ("cannot pull with rebase: You have unstaged changes",
exit 128) whenever the data worktree has unstaged changes — which is close to
permanent when several agents share one `.aitask-data` worktree.

Because it fails *before* the fetch, there is no ref movement of any kind:
neither `origin/<data-branch>` nor the local branch advances, and no reflog
entry is written. Reproduced live during exploration:

```
task data not reconciled with origin/aitask-data: 4 local unpushed, 2 remote unpulled
— data worktree has unstaged changes blocking rebase
SYNC_FAILED:dirty_worktree
```

This is exactly why `ait sync` *does* converge: `aitask_sync.sh auto_commit()`
commits the dirty `aitasks/`/`aiplans/` files **first**, then fetches, rebases
**and pushes**.

### 3. The outcome is discarded

`commit_and_push_from_remote_clone()` calls `sync_current_repo_from_remote`
and ignores it entirely — no `TASK_SYNC_*` inspection, no retry, no report —
then `return 0`. A metadata update that stranded the local branch is
indistinguishable from one that reconciled it.

### 4. There is no push side

`task_sync()` only pulls. Once a local data commit lands on the stale tip the
branch is genuinely **diverged** (ahead N / behind M), and nothing in this path
ever pushes the ahead half. Every subsequent `task_push()` then fails
non-fast-forward — the workflow errors the user sees.

## Evidence

Reconstructed from reflogs (`git reflog show origin/aitask-data`,
`git -C .aitask-data reflog show HEAD`):

```
08:34:16  local commit 5a5a992b0            → pushed 08:34:33, local == remote
08:34:53  temp clone commits dc6f744fb (usage count), pushes   → LOCAL REF UNTOUCHED
08:38:03  syncer's periodic fetch finally notices
08:43:48  local commit 0b0ada411 on the stale tip              → DIVERGENCE CREATED
08:45:40  temp clone commits a17016eda (verified score), pushes
08:46:13  syncer fetch notices → ahead 1 / behind 2
```

Of the 86 occasions where `origin/aitask-data` moved and was discovered by a
plain `fetch` rather than `update by push`, **85 had one of the two metadata
subjects at the tip**. (The 602 `pull --rebase`-labelled updates land on a
metadata commit 600 times — those are the runs where the worktree happened to
be clean, which is what makes the bug intermittent-looking rather than total.)

## Latent hazard in the same seam (in scope to at least guard)

`_ait_detect_data_worktree()` (`lib/task_utils.sh:34`) resolves `.aitask-data`
**relative to the caller's cwd** and falls back to legacy mode `"."` when it is
absent. The fallback is silent and, by design, indistinguishable from a genuine
legacy-mode project.

Within `commit_and_push_from_remote_clone()` the two halves disagree: the push
side uses `./ait git` (which `cd`s to the repo root, always correct) while the
sync side uses `_ait_data_git` (cwd-relative). Reproduced:

- run from `website/` → `task_sync` pulls **`main`**
- run from a crew worktree → pulls **`crew-brainstorm-1017`**

Both report success while the data branch is never reconciled. **None of the 15
scripts that perform data-branch git ops `cd` to the repo root** —
`aitask_archive`, `aitask_artifact`, `aitask_attach`, `aitask_create`,
`aitask_fold_mark`, `aitask_followup_backfill`, `aitask_gate_record`,
`aitask_gate`, `aitask_issue_import`, `aitask_lock`, `aitask_pick_own`,
`aitask_remote_drift_check`, `aitask_sync`, `aitask_update`, `aitask_zip_old`.
Task worktrees are safe (task-workflow Step 5 runs
`aitask_init_data.sh --link-worktree`); crew worktrees are **not** linked —
verified missing on both live crew worktrees.

## Acceptance criteria

1. After a metadata update completes successfully, the **local** data branch
   contains the new commit — no manual sync required. Assert on the local ref,
   not on the remote.
2. The reconcile step survives a **dirty data worktree**: it must not be a bare
   `pull --rebase`. Pick one seam deliberately (`--autostash`, or the
   `auto_commit()` approach `ait sync` already uses) and document why.
3. A failed reconcile is **reported, not discarded** — `commit_and_push_from_remote_clone`
   must inspect the `TASK_SYNC_*` outcome and surface it.
4. Divergence caused by this path is resolved in **both directions**, or the
   task states explicitly why the ahead half is left to `task_push` and shows
   that it converges.
5. Metadata updates are correct when the caller's cwd is **not** the repo root
   — either by anchoring the data-worktree resolution to the repo root, or by a
   loud refusal. A silent fallback to legacy mode from inside a branch-mode
   project must not remain possible.

## Test gap to close

`tests/test_usage_update.sh` + `tests/test_verified_update.sh` are 681 lines
combined and contain **zero** assertions that the local branch converges after
the push — no `task_sync`, no ahead/behind, no `rev-parse`. The single
invariant this bug violates is entirely uncovered. `tests/test_task_git.sh` and
`tests/test_remote_drift_check.sh` pin the presence/absence semantics of
`_ait_detect_data_worktree` from a fixture root, but never the "branch-mode
project, non-root cwd" case.

Add coverage for: local-ref advancement after a successful metadata push; the
dirty-worktree reconcile; and the non-root-cwd resolution.

## Notes

- Related but **distinct**: `t1599` (unscoped `git add` sweeping foreign files
  into a commit) concerns commit *provenance* on the same branch, not
  local/remote convergence. It has children in flight; do not fold.
- The `_task_sync_warn()` policy (`lib/task_utils.sh:354`) is worth a look while
  here: it suppresses its warning when both counts read 0, and those counts are
  read against an upstream ref that a pre-fetch failure never refreshed — so the
  quietest case is the one where nothing happened at all.
