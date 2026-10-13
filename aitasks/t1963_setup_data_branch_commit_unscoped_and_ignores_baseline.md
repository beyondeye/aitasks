---
priority: medium
effort: low
depends: []
issue_type: bug
status: Implementing
labels: [ait_setup, worktree]
gates: [risk_evaluated]
assigned_to: dario-e@beyond-eye.com
anchor: 1711
followup_kind: upstream_defect
created_at: 2026-10-13 08:32
updated_at: 2026-10-13 08:48
---

## Origin

Spawned from t1959 during Step 8b review.

## Upstream defect

- `.aitask-scripts/aitask_setup.sh:1970-1985` — `setup_data_branch` Step 9 ("Commit on main") runs `git add .gitignore`, a global `git diff --cached --quiet`, and an **unscoped** `git commit -m …`. That is a whole-index sweep: anything a concurrent session has staged in this shared checkout rides into "ait: Configure task data branch…" / "ait: Migrate task data to aitask-data branch". It also ignores `AIT_SETUP_DIRTY_BASELINE`, so a user's pre-setup `.gitignore` edit is committed with the data-branch rules.

## Diagnostic context

t1959 made the six `.gitignore` helpers commit path-scoped through `_ait_commit_gitignore_rule` and skip the commit when `.gitignore` is in the dirty baseline (now deletion-aware: `_ait_framework_paths "$project_dir" 1` in `snapshot_pre_setup_dirty`). `setup_data_branch` was left out deliberately: its **migration** branch stages `git rm -r --quiet aitasks/ aiplans/` (~line 1879) and relies on the unscoped commit to carry those removals. A naive `-- .gitignore` pathspec would drop them, and `git commit -- aitasks/` uses `--only` semantics (worktree content), which would pick up the new `aitasks` symlink instead of the deletion. Only runs on a first data-branch setup (it early-returns once `.aitask-data/.git` exists).

## Suggested fix

Commit the exact staged set by name: `.gitignore` plus the paths the `git rm` actually removed (capture them with `git diff --cached --name-only --diff-filter=D -- aitasks aiplans` right after the rm), using `git commit -- <names>` only for paths whose index state is what should land, or commit with a temporary index (`GIT_INDEX_FILE`) built from HEAD + those entries. Skip the `.gitignore` part when it is in `AIT_SETUP_DIRTY_BASELINE` (reuse `_ait_commit_gitignore_rule`'s check). Add tests for both the configure and the migrate branch with a foreign staged file and a dirty `.gitignore`.
