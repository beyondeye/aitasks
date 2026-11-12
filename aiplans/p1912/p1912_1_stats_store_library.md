---
Task: t1912_1_stats_store_library.md
Parent Task: aitasks/t1912_move_codeagent_stats_to_plumbing_branch.md
Sibling Tasks: aitasks/t1912/t1912_*_*.md
Archived Sibling Plans: aiplans/archived/p1912/p1912_*_*.md
Base branch: main
Output branch: main
---

# t1912_1 — Stats store library (plan)

Full spec: `aitasks/t1912/t1912_1_stats_store_library.md`. Parent decisions:
`aiplans/p1912_move_codeagent_stats_to_plumbing_branch.md`.

## Pre-phase (risk mitigations)

1. [relations_store_regression_baseline] Run every relations / orphan-store
   test module (`ls tests | grep -E 'relations|orphan_ref'`). Paste the result
   of each assertion into a `## Baseline` section of this plan. Re-run after
   step 1; any changed result blocks the child.

## Steps

1. `lib/orphan_ref_store.py`: add keyword parameters for the temp-ref prefix
   and the fallback ident, keeping today's values as the defaults. Leave
   relations call sites unchanged.
2. `lib/model_stats_store.py`, pure layer: `bump_usage`, `record_verified`
   (ports of the jq renderers, including the legacy flat → bucketed
   conversion), `merge_buckets`, blob (de)serialization (`schema: 1`, sorted
   keys, 2-space indent, trailing newline).
3. Git layer:
   - `update()`: `fetch_pinned` → render → `build_commit` → `cas_push` with
     a lease, then `advance_ref` on OK. Retry on CONFLICT, ~8 attempts with
     jitter.
   - Remote ABSENT ⇒ create the branch, or push the local branch first.
   - No remote ⇒ `cas_local`.
   - Diverged ⇒ `STATS_DIVERGED`.
   - `refresh()`: probe → `fetch_pinned` → fast-forward
     `refs/heads/aitask-stats`.
   - Loader: reads only `refs/heads/aitask-stats` through one `cat-file`
     batch. Apply the marker rule, then the legacy overlay. The cache holds
     the parsed branch content only, keyed by (realpath common dir, sha);
     recompute the overlay and the merge on every load.
4. CLI `aitask_model_stats.py`: `bump-usage`, `record-verified`, `refresh`,
   `export --agent`, `show`, each with single-line structured output.
5. Wire the refresh into `aitask_sync.sh` after `do_fetch` (stderr only, exit
   code unchanged) and into `aitask_pick_own.sh` `sync_remote`, both
   best-effort.
6. Add `aitask-stats` to the reserved refs: `artifact_registry.RESERVED_REFS`,
   the `seed/project_config.yaml` comment, and the `settings_app` help text.
7. Tests, as listed in the task's Verification section:
   - jq parity driven by the existing writers with `--date`;
   - two-clone concurrency with a seam-forced non-ff;
   - no-remote mode, ABSENT, upgrade and diverged cases;
   - cross-clone visibility under the default, single-branch and negative
     refspecs;
   - `--batch` stdout stays byte-identical when the refresh fails;
   - cache invalidation on a legacy edit, and two projects in one process;
   - `.aitask-data` untouched.

## Verification

- The new tests pass.
- The relations baseline is unchanged.
- `shellcheck` is clean on `aitask_sync.sh` and `aitask_pick_own.sh`.
- The Python suite verdict is PASSED.

## Step 9

Post-Implementation per task-workflow.
