---
priority: medium
effort: low
depends: []
issue_type: bug
status: Implementing
labels: [task_attachments]
assigned_to: dario-e@beyond-eye.com
anchor: 1065
followup_kind: upstream_defect
created_at: 2026-10-22 12:51
updated_at: 2026-10-22 12:54
---

## Origin

Spawned from t2099 during Step 8b review.

## Upstream defect

- `.aitask-scripts/aitask_setup.sh:1691` (`setup_data_branch`) — `git fetch origin aitask-data`
  in a `--single-branch` clone updates no `refs/remotes/origin/aitask-data`, and
  `git branch --track` refuses there; the t2099 test fixture had to set the
  upstream by hand, and setup's own single-branch path was not verified.

## Diagnostic context

t2099 (routine-fetch exclusion for the gitbranch artifact store) builds a fresh
`git clone --single-branch -b main file://…` fixture in
`tests/test_sync_fetch_exclusion.sh` scenario 2, then gives it a data worktree
the way setup would. Two git facts about a single-branch clone surfaced there:

- Its fetch mapping is `+refs/heads/main:refs/remotes/origin/main` only, so
  `git fetch origin aitask-data` (setup's form, which has no destination) writes
  `FETCH_HEAD` and updates no remote-tracking ref; nothing creates
  `refs/remotes/origin/aitask-data`.
- `git branch --track aitask-data origin/aitask-data` fails with "cannot set up
  tracking information; starting point 'origin/aitask-data' is not a branch",
  because the start point does not match the remote's fetch refspec.

The fixture works around both: it fetches into an explicit
`+refs/heads/aitask-data:refs/remotes/origin/aitask-data` refspec, creates the
branch without `--track`, and sets `branch.aitask-data.remote` /
`branch.aitask-data.merge` by hand. Whether `setup_data_branch` (the
`git worktree add .aitask-data aitask-data` DWIM path, and the upstream that
`ait sync` needs for `@{u}`) works in a `--single-branch` clone was never
verified. The t1890 design (`aidocs/artifact_storage_lifecycle.md` §3)
recommends `--single-branch` clones precisely to keep the artifact store out.

## Suggested fix

Reproduce `ait setup` in a `--single-branch` file:// clone of a repo with an
`aitask-data` branch. If it breaks, fetch with the explicit refspec and set the
branch upstream explicitly, as the t2099 fixture does.
