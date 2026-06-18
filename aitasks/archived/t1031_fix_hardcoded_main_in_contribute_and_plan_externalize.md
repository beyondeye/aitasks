---
priority: medium
effort: low
depends: []
issue_type: bug
status: Done
labels: [framework, git]
assigned_to: dario-e@beyond-eye.com
anchor: 1027
created_at: 2026-06-18 15:34
updated_at: 2026-06-18 16:37
completed_at: 2026-06-18 16:37
---

## Origin

Spawned from t1027 during Step 8b review. t1027 fixed the hardcoded `main`
primary-branch assumption in `desync_state.py` + the syncer, but the plan
review surfaced two more hardcoded-`main` references in unrelated scripts that
break (or write wrong metadata) in a `master`-default repo (e.g. the sibling
`aitasks_mobile` project). These were out of scope for t1027 (separate
features) but are the same defect class.

## Upstream defect

- `aitask_contribute.sh:448` — `git diff --name-only main -- <dirs>` in
  clone/project contribution mode. In a `master`-default repo `main` does not
  exist, so the diff returns nothing (the `|| true` swallows the error) and
  contribution mode silently finds no changed files.
- `aitask_plan_externalize.sh:307` — always emits `Base branch: main` in the
  plan metadata header (and only suppresses the `Branch:` line when the current
  branch equals the literal `main`). In a `master`-default repo the plan header
  records the wrong base branch.

## Diagnostic context

Root cause is identical to t1027: a hardcoded `"main"` literal where the
repository's actual primary branch should be resolved dynamically. t1027 added
`detect_primary_branch(worktree)` to `.aitask-scripts/lib/desync_state.py`
(resolution order: `git symbolic-ref --quiet --short refs/remotes/origin/HEAD`
→ local `main`→`master` probe → `"main"` fallback). That helper, or the same
git-native `symbolic-ref` approach, is the reusable building block for these
sites.

Note: `create_new_release.sh:30` also hardwires releases to `main`, but it is a
root-level release tool for the aitasks framework itself (this repo is
main-default) and is considered intentional — excluded from this task's scope.

## Suggested fix

For `aitask_plan_externalize.sh`: resolve the base branch dynamically (reuse
the `detect_primary_branch` logic — extract it to a shared shell/py helper or
shell out to `desync_state.py`) instead of the `main` literal, and gate the
`Branch:` suppression on the resolved branch rather than the literal `main`.
For `aitask_contribute.sh`: diff against the resolved primary branch instead of
`main`. Add tests covering a `master`-default fixture, mirroring t1027's
`tests/test_desync_state.py::test_master_default_repo_reports_up_to_date`.
