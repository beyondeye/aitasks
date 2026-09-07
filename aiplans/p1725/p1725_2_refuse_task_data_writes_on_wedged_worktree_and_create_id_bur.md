---
Task: t1725_2_refuse_task_data_writes_on_wedged_worktree_and_create_id_bur.md
Parent Task: aitasks/t1725_sync_deferrals_actionable_and_safe_to_continue.md
Sibling Tasks: aitasks/t1725/t1725_1_*.md, aitasks/t1725/t1725_3_*.md, aitasks/t1725/t1725_4_*.md, aitasks/t1725/t1725_5_*.md, aitasks/t1725/t1725_6_*.md
Archived Sibling Plans: aiplans/archived/p1725/p1725_*_*.md
Base branch: main
Output branch: main
---

# t1725_2 — refuse task-data writes on a wedged worktree; stop `create` burning ids

Parent plan: `aiplans/p1725_sync_deferrals_actionable_and_safe_to_continue.md`,
section "Child 2". Findings 6, 7 / AC4, AC5. No sibling dependency.

## Context

Mid-rebase, the checked-out task file is origin's version, not the branch tip; no
writer checks before `sed`-ing (finding 6: a risk-gate write landed on t1717's stale
`Ready` version). `ait create --batch --commit` dies when its commit fails, leaves the
file, and each retry claims a fresh id (finding 7: t1722/t1723/t1724). Scope decision
(parent plan): the wedge is the one production-reachable way the base differs, so a
refusal there is the AC's "refused, not applied blind"; no per-writer base SHA.

Sibling overlap: t1599_4 (Implementing) owns commit *scoping* in `aitask_create.sh` /
`aitask_update.sh`. This task adds a pre-write guard and a commit-failure branch —
no shared lines; rebase rather than hand-merge if both land close together.

### Pre-phase (risk mitigations)

1. [writer_entry_point_table] Write `tests/test_task_data_writer_guard.sh` as a table
   **before** adding any guard call: one row per task-data writer
   (`aitask_update.sh --batch <id> --priority low`, `aitask_create.sh --batch --commit
   --name x …`, `aitask_note.sh <id> --from t1 --text x`, the `aitask_gate.sh` ledger
   append verb, `aitask_archive.sh …`, `aitask_plan_externalize.sh <id> …`) against the
   planted-wedge fixture — non-zero exit, the guard's message, unchanged bytes
   (md5) — plus one row per exempt read-only script (`aitask_ls.sh`,
   `aitask_query_files.sh resolve <id>`, `aitask_lock.sh --check <id>`) asserting it
   still runs. Enumerate candidates with
   `grep -ln 'sed_inplace\|>> *"\$\|write_task_file\|mv ' .aitask-scripts/*.sh`; list the
   audited-but-not-guarded scripts (metadata-only / read-only) in the plan's Final
   Implementation Notes. The rows fail until step 3 lands — commit together.

## Steps

2. `task_utils.sh`: `assert_task_data_writable()` — return 0 under
   `AIT_GIT_SKIP_STATE_CHECK=1`; when `_data_wedge_state` (from t1725_1; add it here
   with the same contract if t1725_1 has not landed) is non-empty, `die`:
   "Data worktree (.aitask-data) is mid-<state>: the checked-out task files are not
   the branch tip, so writing now would land on stale content. If a sync is running
   right now, retry in a few seconds. Otherwise: ./ait git rebase --abort (discards
   only the partially replayed remote commits; your committed work stays) or resolve
   and ./ait git rebase --continue. './ait git-health' shows the full state."
3. Call it at every writer entry in the table: `aitask_update.sh` (`run_batch_mode`
   before `resolve_task_file` ~1846; `run_interactive_mode` ~1589),
   `aitask_create.sh` (`--batch --commit` branch ~2193 **before** `acquire_child_lock`
   / `claim_unique_parent_id`; `finalize_draft` ~817; interactive commit ~2050),
   `lib/ledger_block.sh` (append entry — covers `aitask_gate.sh` and `aitask_note.sh`),
   `aitask_archive.sh`, `aitask_plan_externalize.sh`. Drafts in `aitasks/new/` are
   not guarded (no id, no commit).
4. `aitask_create.sh` commit failure after the file is written (parent and child
   branches; release the child lock first): keep the file, print the path on stdout
   exactly as on success, warn on stderr "task file written but NOT committed (<first
   non-blank git line>) — it will be swept into the next sync's auto-commit under its
   own task id; do not re-run create", skip `run_auto_merge_if_needed`, exit 0.
5. `shellcheck` the touched scripts.

## Verification

`tests/test_task_data_writer_guard.sh` (fixtures: `tests/test_task_git.sh` ~868 plants
`rebase-merge`; `tests/test_create_silent_stdout.sh` has the bare-remote + claim-id
scaffold):
- F6: local commit with `status: Implementing` + `active_gates`; planted wedge with the
  checked-out file at the stale `Ready` version → `aitask_update.sh --batch <id>
  --risk-code-health low` exits non-zero, message names retry / abort, bytes unchanged,
  nothing committed. Negative control: clean worktree → the update succeeds.
- F7 wedge: `aitask_create.sh --batch --commit` exits non-zero before claiming —
  `aitask_claim_id.sh --peek` identical before/after, no file written.
- F7 commit failure: planted `index.lock` → path printed, exit 0, stderr "NOT
  committed", `--peek` +1 exactly; remove the lock, `aitask_sync.sh --batch` commits it
  under `ait: Auto-commit t<id> task data before sync`.
Run the new file plus `tests/test_create_silent_stdout.sh`, `tests/test_task_git.sh`,
`tests/test_update_check.sh`.

## Step 9

Standard post-implementation; parent t1725 archives after the last child.
