---
priority: high
effort: high
depends: []
issue_type: enhancement
status: Ready
labels: [git, concurrency, verifiedstats, models, robustness]
file_references: [.aitask-scripts/lib/verified_update_lib.sh:120-292, .aitask-scripts/aitask_usage_update.sh, .aitask-scripts/aitask_verified_update.sh, .aitask-scripts/lib/stats_data.py:528-760, .aitask-scripts/lib/agent_model_picker.py]
anchor: 1599
created_at: 2026-10-07 17:46
updated_at: 2026-10-07 17:46
---

## Problem

The code-agent usage and verified-score counters (`usagestats`, `verifiedstats`,
`verified` in `aitasks/metadata/models_<agent>.json`) live on `aitask-data`, and
are written there in a way that keeps `origin/aitask-data` ahead of the shared
`.aitask-data` worktree almost all the time.

Every completion writes them twice (usage + verified). Each write clones
`origin/aitask-data` into a temp dir, commits there and pushes straight to origin
(`lib/verified_update_lib.sh`, `commit_and_push_from_remote_clone` ~L168). Then it
converges the shared worktree (`task_data_converge`, `lib/task_utils.sh` ~L1596),
both before the clone and after the push (`commit_metadata_update` ~L245). So on a
single machine, stats commits are the main thing that puts origin ahead of local.
Every "origin ahead" state is a rebase or fast-forward of the one worktree and one
index that every session on the machine shares.

The counters themselves rarely conflict. The problem is that they cause the
rebase windows in which the trail-1725 bugs happen:

- while `.aitask-data` is mid-rebase, every other session's task write dies in
  `assert_data_worktree_clean` (t1725 finding 5);
- `_rebase_blocked` (`aitask_sync.sh` ~L1504) can only defer when
  `remote_ahead > 0`, and on one machine that is mostly stats commits;
- the converge can come back `diverged` and strand a metadata commit (see
  `cd994a6ef`, "Converge aitask-data with stranded origin metadata commits",
  2026-09-04).

## Evidence

Measured on 2026-10-07 from **one machine's** `.aitask-data` reflog
(2026-06-28 → 2026-10-07). Each `(start)` rebase was replayed with
`git merge-tree --write-tree <onto> <orig-head>`. Another machine's rebases (e.g.
Darios-Mac-mini) are not visible in this reflog, only its merge commits.

| measure | value |
|---|---|
| data-branch commits since 06-28 that are `Update usage count` / `Update verified score` | 1,384 of 8,180 (17%) |
| rebase cycles of the shared worktree | 307 |
| … where origin's extra commits were **only** stats commits | 269 (88%) |
| … that included any stats commit | 294 (96%) |
| … that contained no stats commits at all | 13 |
| fast-forward converges (`merge origin/aitask-data: Fast-forward`) | 282, of which 275 only stats |
| cycles with a real textual conflict | 8 |

The 8 conflicts:
- **4 in `models_claudecode.json`, all 07-29 to 08-04.** Every one came from a
  *local* commit of the stats file in the shared worktree: three from the old
  catch-all sweep ("Auto-commit task changes before sync", `9cf496c57`), one from
  a hand commit "Update verified scores and usage stats" (`6abff981c`). These
  clashed with the clone-pushed stats commits. Scoped commits (t1728) and the
  protected sweep (t1599_3) closed this. No stats conflict since 08-04.
- **4 in task files** (t1705 ×3 on 09-06/07, t1688 on 09-14), plus one manual
  merge on t1828 (09-17, `29dbbb593`). These are real concurrent frontmatter
  edits and are **not** in scope here (t1727 automerge, t1459).

Artifacts were checked as well: `artifacts/manifests/` and `attachments/` had zero
conflicts, and only about 37 artifact commits since July. They stay on
`aitask-data` (see Non-goals).

## Goal

Move the counters off `aitask-data` so a stats update never fetches, merges,
rebases or pushes the shared `.aitask-data` worktree, and never stages anything in
its index. Readers keep showing the same numbers.

## Design direction (decisions for planning)

1. **Copy the plumbing-branch design of `aitask-locks` / `aitask-ids`.** Write with
   `hash-object` / `mktree` / `commit-tree`, push the commit, and on a
   non-fast-forward rebuild from the re-read origin tip and retry
   (`aitask_lock.sh` ~L300-330, `aitask_claim_id.sh`). No worktree, no index, no
   checkout, so it cannot get stuck mid-rebase and cannot be swept into a task
   commit. Setup/registration follows the existing lock/ids branch bootstrap in
   `aitask_setup.sh` (~L1154-1270). Read
   `aidocs/framework/aitasks_extension_points.md` before editing setup.
2. **Data model.** Two options; planning picks one:
   - (a) per-(agent, model) counter blobs, read-modify-write, recomputed on the
     origin tip on each retry (smallest change, same shape as today);
   - (b) **recommended:** one small append-only file per completion event
     (agent, model, skill, score, timestamp, host). The week / month / prev_month /
     all_time windows are computed on read. Concurrent writers add different
     paths, so the retry is a pure re-parent and there is no period-rollover
     logic. Planning must say whether this needs a compaction/snapshot step for
     read cost.
3. **Split `models_<agent>.json`.** Registry fields (`name`, `cli_id`, `notes`, …)
   stay on `aitask-data`. `usagestats` and `verifiedstats` move. Decide what
   happens to `verified`: it is the legacy per-operation score, initialised by
   `aitask_add_model.sh` (~L138, ~L159) and seeded/preserved by
   `aitask_opencode_models.sh` (~L160, ~L200).
4. **One shared read path.** Today four readers load the stats keys straight from
   the worktree file: `lib/stats_data.py` (verified rankings ~L528, usage rankings
   ~L702), `lib/agent_model_picker.py` (~L359, ~L396, ~L566),
   `settings/settings_app.py` (`_aggregate_verifiedstats` ~L475, ~L2132,
   ~L3190) and `aitask_codeagent.sh` (jq ~L332). Give them one loader over the
   local stats ref, e.g. `git cat-file` or a gitignored materialised cache. TUIs
   must not pay a fetch per render.
5. **Migration and version skew.** A one-time, idempotent move of the existing
   counters into the new branch, then strip the stats keys from `models_*.json`
   in one scoped commit. Name the path this runs on (`ait setup` / `ait upgrade`,
   picked by intent). A framework copy older than this change (e.g. the other
   machine before it upgrades) still writes counters into `models_*.json`.
   Planning decides between a hard cutover and readers summing both sources for
   a transition window.
6. **No-remote mode.** Keep a local-only path, as `aitask_claim_id.sh` does for
   its local counter.
7. **Side effect to keep or re-home.** `converge_current_repo_with_remote`
   (`verified_update_lib.sh` ~L120) *pushes as well as pulls*, so today a stats
   update also publishes any unpushed local task-data commits. Find out whether
   any workflow step relies on that publication before removing the converge.
   If one does, move that publish to an explicit `./ait git push` / sync at that
   step, not to the stats writer.
8. **Cross-repo settings.** `lib/cross_repo_settings.py` (~L378) reads
   `models_<agent>.json` in a destination repo. Confirm it never carries stats
   keys across, or update it to follow the split.

## Non-goals

- Task/plan frontmatter conflicts (t1727 automerge, t1459 field-level causality).
- Shared-index races and lock adoption (t1678), and deferral UX (t1725_5..7).
- Artifacts and attachments: zero measured conflicts. The task frontmatter keeps
  the `artifacts:` handle list anyway, so a split would make create/rm span two
  branches and could not be atomic.
- This does not stop the shared worktree from rebasing on task commits pushed
  from another machine (13 + 25 mixed cycles in the sample). It removes the
  stats-driven ones.

## Acceptance criteria

- A usage or verified update leaves `.aitask-data` HEAD, index and
  `git status --porcelain` byte-identical, pinned with the worktree dirty
  (modified tracked file + untracked file) and with origin ahead. The test also
  pins that no fetch/merge/rebase/push of `aitask-data` ran.
- Two concurrent updates for the same agent/model/skill from two clones both
  land, and the totals equal the sum. No lost increment, including across a
  forced non-fast-forward retry.
- On a fixture, the stats TUI rankings, settings view, agent picker and
  `aitask_codeagent.sh` listing show the same values before and after migration.
- Migration is idempotent: running it twice does not double any count. After it,
  `models_*.json` holds no stats keys, and `aitask_add_model.sh` /
  `aitask_opencode_models.sh` do not re-add them.
- No-remote mode records and reads stats.
- Existing suites still pass, updated where they pin the old storage:
  `test_usage_update.sh`, `test_verified_update.sh`,
  `test_verified_update_flags.sh`, `test_metadata_commit_seam.sh`,
  `test_stats_verified_rankings.sh`, `test_stats_data.sh`,
  `test_aitask_stats_py.py`.

## Post-landing measurement

After a couple of weeks of normal multi-agent use, replay the `.aitask-data`
reflog the same way as the Evidence section (each `(start)` →
`git merge-tree --write-tree`). Report rebase cycles and fast-forward converges
whose remote-only commits are stats commits. Expected: none, unless the other
machine is still on an old version.

## Related

- t1725 trail (`art:trail-parallel-git-and-sync`): membership is an explicit list,
  so this task joins it only on a trail refresh.
- t1714 (shared metadata write mutex): its scope shrinks if counters leave
  `models_*.json`. Re-check it after this lands.
- t1678 (data-index lock adoption): once this lands, the stats writers' local
  commit path and their pre/post converge no longer touch the shared index or
  worktree. If t1678 is planned first, it should not spend effort locking them.
