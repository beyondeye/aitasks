---
priority: medium
effort: medium
depends: [t1725_1]
issue_type: enhancement
status: Implementing
labels: [git, bash_scripts, robustness, syncer]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
anchor: 1599
created_at: 2026-09-07 17:51
updated_at: 2026-09-08 15:44
boardcol: now
boardidx: 31814
---

## Problem

The framework has two `pull --rebase` paths on the task-data branch and only one
of them can resolve a conflict:

- `aitask_sync.sh` (`ait sync` / the syncer's and board's `s`): on a conflict it
  runs `try_auto_merge` (~901) — `board/aitask_merge.py --batch --rebase` with the
  merge base from the conflicted index (stage 1) — advances the rebase with
  `_rebase_advance` (~982), and reports `AUTOMERGED`. Frontmatter-only collisions
  (`updated_at` vs `boardcol`/`boardidx`, gate-ledger appends — `tests/test_sync.sh`
  Tests 12–15) resolve without a human.
- `task_utils.sh:_task_pull_rebase` (~787) — the pull every **pick** runs
  (`task_sync`, via `aitask_pick_own.sh` at claim / `--sync` / the Step 7 ownership
  guard) and every **push retry** runs (`task_push`, `aitask_pick_own.sh:498`,
  `ait git push`) — is a bare `_ait_data_git pull --rebase --quiet`. The same
  frontmatter collision that `ait sync` would auto-merge fails here.

Once t1725_1 lands the failure is at least *clean* (the rebase is aborted,
`SYNC_FAILED:rebase_conflict`, nothing wedged) — but still unresolved: the pick
proceeds against a stale data branch until someone runs `ait sync`, and the
`task_push` retry loop burns its three attempts on a conflict it cannot clear, so
the claim / gate / archive commit stays unpushed.

## Grounding (data branch, 2026-09-07)

- `./ait git reflog` shows **43 `pull --rebase` cycles** on `aitask-data` today
  (108 commits), 2 of them aborted and one — the 09:30 replay of 21 commits — only
  completed by a manual `rebase (continue)` through
  `ait: Auto-commit t1705 task data before sync` (`updated_at` vs
  `boardcol`/`boardidx`, bodies identical). That is the t1717 wedge recorded in
  t1725 finding 5; it started from the workflow's pull, not from `ait sync`.
- The lock branch holds locks from two hosts (`omg16` ×11,
  `Darios-Mac-mini.local` ×1): with two PCs, `remote_ahead > 0` at pick time is the
  normal case, so every pick-time pull is a candidate for exactly this conflict.
- t1676 (Done) and t1725_1 harden *how* the two paths fail; nothing makes the
  workflow path *resolve*.

## Goal

`task_sync` and `task_push` resolve the conflicts `ait sync` already resolves,
through the **same** merge driver and the **same** advance/abort logic — one
implementation, two callers — while keeping their best-effort contracts (always
return 0; outcome in the `TASK_SYNC_*` / `TASK_PUSH_*` globals; one `warn` on
failure).

## Suggested shape (not prescriptive)

1. Extract `try_auto_merge` + `_rebase_advance` (+ `_resolve_conflict_path`, the
   `_MERGE_PYTHON` / `_MERGE_SCRIPT` resolution) from `aitask_sync.sh` into a
   sourced library (e.g. `lib/task_automerge.sh`) with no dependency on the sync
   script's globals (`BATCH_MODE`, `iinfo_err`): stdout stays the unresolved-file
   list, diagnostics go to stderr. `aitask_sync.sh` sources it; behaviour and the
   `AUTOMERGED` token are unchanged (`tests/test_sync.sh` 12–15 pin it).
2. `_task_pull_rebase`: on a conflicted pull, run the library's auto-merge and
   advance loop; if every conflict resolves, treat the pull as successful and set
   a new `TASK_SYNC_AUTOMERGED=1` / `TASK_PUSH_AUTOMERGED=1`; if anything remains,
   fall through to t1725_1's abort (nothing left in progress). Source the library
   lazily, the way `pid_anchor.sh` sources `tmux_exec.sh` — `task_utils.sh` is
   copied standalone into test fixtures and a missing library must degrade to
   "no auto-merge", never break sourcing.
3. Surface it: `aitask_pick_own.sh --sync` prints `SYNCED` as today (the
   cross-process token vocabulary is documented in
   `website/content/docs/commands/sync.md`; decide whether a `SYNCED:automerged`
   detail is worth adding to it — if so, update every consumer and the doc in the
   same commit); `task_push_report` likewise. A one-line stderr notice
   ("auto-merged N frontmatter conflict(s) during sync") is enough for the human.
4. The `task_push` retry loop: an auto-merged rebase counts as progress, not as a
   failed attempt.

## Acceptance criteria

- A frontmatter-only conflict (local `updated_at` vs remote `boardcol`/`boardidx`
  on the same task file; bodies identical) during `aitask_pick_own.sh --sync`
  converges: `SYNCED`, both sides' fields present in the result, `HEAD..@{u}` and
  `@{u}..HEAD` both 0, no `rebase-merge` left behind. Same through `task_push`'s
  retry (a claim commit pushed after the auto-merge).
- A body conflict still fails the same way t1725_1 leaves it: aborted, reason
  `rebase_conflict`, worktree clean — pinned as the negative control.
- `ait sync --batch` on the same fixtures still reports `AUTOMERGED` — the
  extraction changed nothing there (`tests/test_sync.sh` 12–15,
  `tests/test_sync_branch_mode_automerge.sh`).
- `task_utils.sh` sourced without the library present still works (the
  standalone-fixture case): pull-rebase conflicts fail as before, no error on
  source.
- Tests in `tests/test_task_push.sh` (its `setup_branch_mode` fixture already
  builds the two-clone conflict).

## Key files

- `.aitask-scripts/lib/task_utils.sh` — `_task_pull_rebase` (~787), `task_sync`
  (~606), `task_push` (~745), `task_push_report`, `_task_push_classify`
- `.aitask-scripts/aitask_sync.sh` — `try_auto_merge` (~901), `_rebase_advance`
  (~982), `_resolve_conflict_path` (~1141), `_MERGE_PYTHON` / `_MERGE_SCRIPT` (~59)
- `.aitask-scripts/board/aitask_merge.py` — the driver (`--batch --rebase
  --base-file`)
- `.aitask-scripts/aitask_pick_own.sh` — `sync_remote` (~198), the `SYNCED` /
  `SYNC_FAILED` lines (~511)
- `.aitask-scripts/lib/pid_anchor.sh:_anchor_tmux_pane_pid` — the lazy-source pattern
- `tests/test_task_push.sh`, `tests/test_sync.sh`, `tests/test_sync_branch_mode_automerge.sh`

## Related

- t1725_1 (abort a conflicted `_task_pull_rebase`) — this task builds on its
  abort path: auto-merge first, abort only what auto-merge cannot resolve.
  `depends: [1725_1]`.
- t1725_3 (fast-forward instead of rebase when nothing local is ahead) — removes
  the conflict-free half of the same pulls.
- t1676 (Done) — the sync-side conflict loop dying mid-rebase.
