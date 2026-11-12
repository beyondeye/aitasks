---
Task: t1912_4_stats_writer_cutover.md
Parent Task: aitasks/t1912_move_codeagent_stats_to_plumbing_branch.md
Sibling Tasks: aitasks/t1912/t1912_*_*.md
Archived Sibling Plans: aiplans/archived/p1912/p1912_*_*.md
Base branch: main
Output branch: main
---

# t1912_4 — Stats writer cutover (plan)

Full spec: `aitasks/t1912/t1912_4_stats_writer_cutover.md`.

## Steps

1. Write the acceptance test first (red against the current writers):
   - `.aitask-data` dirty (a modified tracked file plus an untracked file)
     and origin ahead;
   - the update must leave HEAD, the `ls-files -s` hash and
     `status --porcelain` byte-identical;
   - a PATH git wrapper must log no fetch/merge/rebase/pull/push of
     `aitask-data`.
2. Rewrite the `aitask_usage_update.sh` / `aitask_verified_update.sh` bodies:
   - keep arg parsing and validation, and keep the registry model-exists
     check read-only;
   - call `aitask_model_stats.py bump-usage` / `record-verified`;
   - map the outputs to `UPDATED:` / `STATS_ERROR:`;
   - stop writing `verified`.
3. Remove `commit_metadata_update*`, the clone path and both converges.
   Shrink `verified_update_lib.sh` after grepping its sourcers. Keep
   `registry_cas.sh`.
4. satisfaction-feedback: drop `UPDATED_REMOTE_ONLY` and add `STATS_ERROR`
   as warn-and-continue. Then rerender, regenerate the goldens and verify.
5. Decide whitelist entries for `aitask_model_stats.py` (only needed if a
   skill invokes it) and record the decision.
6. Update or retire the listed tests, giving a reason for each retirement.

## Verification

- The acceptance test is green.
- The listed suites pass.
- shellcheck is clean.
- The Python verdict is PASSED.
- Manual smoke in this repo: `.aitask-data` is unchanged and `show` reflects
  the bump.

## Step 9

Post-Implementation per task-workflow.
