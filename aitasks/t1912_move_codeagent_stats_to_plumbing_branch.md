---
priority: high
effort: high
depends: []
issue_type: enhancement
status: Implementing
labels: [git, concurrency, verifiedstats, models, robustness]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 4a36c12bb96d.681bafac2cb9.d73bba2fc21f
file_references: [.aitask-scripts/lib/verified_update_lib.sh:120-292, .aitask-scripts/aitask_usage_update.sh, .aitask-scripts/aitask_verified_update.sh, .aitask-scripts/lib/stats_data.py:528-760, .aitask-scripts/lib/agent_model_picker.py]
children_to_implement: [t1912_1, t1912_2, t1912_3]
assigned_to: dario-e@beyond-eye.com
anchor: 1599
created_at: 2026-10-07 17:46
updated_at: 2026-11-12 19:42
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
- t1696 (in flight): fixes the recovery hint for the `UPDATED_REMOTE_ONLY`
  partial outcome of exactly these writers (`verified_update_lib.sh`,
  `aitask_usage_update.sh`, `aitask_verified_update.sh`, their tests). Plan this
  task against t1696's landed code. Once counters stop being pushed into
  `aitask-data` from a clone, that partial-outcome class should disappear for
  stats. Say so in the plan instead of carrying it forward.
- t1910 (in flight): edits `aitask_add_model.sh`, `aitask_codeagent.sh`,
  `lib/agent_model_picker.py`, `settings_app.py` and `aitask_setup.sh`, all
  touchpoints here.
- t1678 (data-index lock adoption): once this lands, the stats writers' local
  commit path and their pre/post converge no longer touch the shared index or
  worktree. If t1678 is planned first, it should not spend effort locking them.

## Inbox
<!-- Appended by the note framework. Do not edit by hand; use `./ait note`. -->

> **✉ note:t1919** id=2026-10-09T08:41:59Z.f6d2dd04742d34514b91d2fe from=t1919 from_verified=yes at=2026-10-09T08:41:59Z base=dfa4d47b15f4bb77258ba081382670dab0b8532b base_branch=main dirty=yes host=omg16
>
> | t1919 (committed dfa4d47b1 on main) changed the opencode refresh merge your task body cites as "seeded/preserved by aitask_opencode_models.sh (~L160, ~L200)":
> | 
> | - ~L200 (merge_with_existing, rediscovered rows) no longer hand-picks `verified`/`verifiedstats`. It now overlays the existing row minus the discovery-owned `name`/`cli_id`/`notes`/`status` (nulls dropped). So it carries `usagestats` and any other non-owned field too. Once the counters move off models_*.json, this branch cannot re-add them, because it only carries what is already on the row.
> | - ~L160 (new-row defaults in process_model) still writes `"verified": {...0}` and `"verifiedstats": {}` for newly discovered models. That is the only place the refresh would re-add a stats key, so the "does not re-add them" acceptance item should target it.
> | - Pinned by tests/test_opencode_models_merge.sh (5 cases) — update it if the stored fields move.
> | - t1928 (refresh vs. counter-writer last-writer-wins race on models_opencode.json) becomes moot for every counter this task moves out of the file. Consider it when planning, or fold it in.
> | 
> | Line numbers are as of dfa4d47b1.

> **✉ note:t2194** id=2026-11-04T14:54:51Z.f8dc92c443a9fe43a949a3f1 from=t2194 from_verified=yes at=2026-11-04T14:54:51Z base=c0a6bbd4015d48cca47bfd7b1deba187cfb4c66f base_branch=main dirty=yes host=omg16
>
> | Advisory context from t2194 (code commit 11cb4d3d5 on main), relevant to item 4 "One shared read path":
> | 
> | 1. There is now a shared, stdlib-only helper for the date-correct windows:
> |    `.aitask-scripts/lib/model_stats_windows.py` — `resolve_windows(buckets, today)`,
> |    `recent_aggregate(buckets, today)`, `current_periods(today)`,
> |    `stats_key_for_operation(op)`. Rule: a stored month/prev_month/week bucket counts only
> |    when its `period` equals that window's period computed from today (ISO `%G-W%V` weeks,
> |    as the writers stamp); an un-rolled `month` bucket from last month counts as prev_month.
> |    If t1912 picks design (b) (per-event files, windows computed on read), this module is
> |    the natural place for that computation; if (a), every reader should still go through it.
> | 
> | 2. The reader line numbers t1912 cites are stale as of 11cb4d3d5:
> |    - `lib/agent_model_picker.py`: the "~L359/~L396/~L566" readers are now
> |      `_build_top_all_ops` / `_build_top_usage` / `_build_options_for_agent` (the
> |      "Top verified" list was replaced by "Top used models (recent, all ops)").
> |      The picker's private `_recent_aggregate` copy is gone.
> |    - `lib/stats_data.py`: `load_verified_rankings` / `load_usage_rankings` take
> |      `today=`, store resolved windows and sum them across providers; the duplicate
> |      `recent_aggregate` is now a re-export of the helper.
> |    - `settings/settings_app.py` `_aggregate_verifiedstats(today=)` sums resolved windows.
> | 
> | 3. Reader-side key mapping: `batch-review` reads the counters recorded under `review`
> |    (`STATS_KEY_BY_OPERATION`). A new shared loader should keep applying it where
> |    counters are looked up by codeagent operation.
> | 
> | 4. The jq reader in `aitask_codeagent.sh` (`list-models`, ~L337) reads the pre-bucket
> |    flat format and always prints `runs 0, avg 0`; spawned as t2200.
> | 
> | These are claims about the tree at 11cb4d3d5, not instructions.

> **✉ note:t2200** id=2026-11-04T16:52:37Z.2fd1ac5660eb82cd6499c38a from=t2200 from_verified=yes at=2026-11-04T16:52:37Z base=b35ee6bb9459499835b39881eef612688860434e base_branch=main dirty=yes host=omg16
>
> | Update on item 4 of the t2194 note in this inbox (the `list-models` jq reader in
> | `.aitask-scripts/aitask_codeagent.sh`): t2200 fixed it in commit b35ee6bb9.
> | 
> | - `cmd_list_models` now reads `verifiedstats.<op>.all_time.{runs,score_sum}`,
> |   falling back to a flat `{runs, score_sum}` entry (same rule as
> |   `lib/stats_data.py`). The filter sits at roughly L337-352 as of b35ee6bb9.
> | - STATS line format unchanged: `STATS:pick(runs N, avg M),...`, all-time only
> |   (no recent window).
> | - `tests/test_codeagent.sh` Test 4b pins the STATS line for a synthetic
> |   bucketed / flat / mixed / no-stats `models_claudecode.json` fixture.
> | 
> | Why it may matter here: this reader is still one t1912's shared read path is
> | meant to replace. Its "same values before and after migration" acceptance
> | check on the `aitask_codeagent.sh` listing now compares real all-time numbers.
> | Before this fix it would have compared zeros on both sides. Test 4b is a
> | ready-made fixture for that parity check if useful. Advisory only.

> **👁 note:read** id=2026-11-12T06:59:36Z.675ededc7d04c1241f4f0d23 by=t1912 at=2026-11-12T06:59:36Z mode=explicit ids=2026-10-09T08:41:59Z.f6d2dd04742d34514b91d2fe,2026-11-04T14:54:51Z.f8dc92c443a9fe43a949a3f1,2026-11-04T16:52:37Z.2fd1ac5660eb82cd6499c38a
