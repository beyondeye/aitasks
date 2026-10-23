---
priority: low
risk_code_health: low
risk_goal_achievement: low
effort: low
depends: []
issue_type: bug
status: Implementing
labels: [git, bash_scripts]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
followup_kind: upstream_defect
implemented_with: claudecode/opus5_5
created_at: 2026-10-22 10:52
updated_at: 2026-10-23 00:23
---

## Origin

Spawned from thinking_backend#t65 during Step 8b review (a downstream project
that vendors this framework at v0.39.0). Not a task in this repository.

## Upstream defect

- `.aitask-scripts/lib/git_utils.sh:22` — `detect_primary_branch()` reads
  `git symbolic-ref --quiet --short refs/remotes/origin/HEAD`. `--short`
  abbreviates by ambiguity: when a local branch named `origin/main` exists, it
  answers `remotes/origin/main` instead of `origin/main`, the
  `${head#origin/}` strip then misses, and `remotes/origin/main` is returned
  as the "primary branch".

Reproduced (git 2.56):

```bash
git init -q -b main && git commit -q --allow-empty -m i
git update-ref refs/remotes/origin/main HEAD
git symbolic-ref refs/remotes/origin/HEAD refs/remotes/origin/main
git symbolic-ref --quiet --short refs/remotes/origin/HEAD   # origin/main
git branch origin/main
git symbolic-ref --quiet --short refs/remotes/origin/HEAD   # remotes/origin/main
source .aitask-scripts/lib/git_utils.sh; detect_primary_branch   # remotes/origin/main
```

`.aitask-scripts/lib/desync_state.py:detect_primary_branch` mirrors this
resolution order (see the t1031 cross-reference comment above the bash
function) — check it for the same issue.

## Diagnostic context

thinking_backend#t65 fixed the same `--short` class for HEAD in
`aitask_plan_externalize.sh`: with a tag `dev` beside branch `dev`,
`git symbolic-ref --short HEAD` answers `heads/dev`, which was written into the
plan header and then looked up by `aitask_remote_drift_check.sh` as
`refs/heads/heads/dev`. The fix there reads the full ref and strips
`refs/heads/`. The same review noticed this sibling in `detect_primary_branch`.
The trigger (a local branch literally named `origin/main`) is contrived, so
impact is low, but the primary branch feeds plan headers and merge targets.

The t65 helper/doc patch itself (current-branch mode records the checked-out
branch instead of the primary; `Branch:` = `aitask/<task_name>` in worktree
mode) is a separate handoff and is not part of this task.

## Suggested fix

Read the full target (`git symbolic-ref --quiet refs/remotes/origin/HEAD`) and
strip `refs/remotes/origin/`, accepting the value only when that prefix
matched; keep the existing `main`/`master` fallbacks. Apply the same change to
the Python mirror, and add a regression case with a local `origin/main` branch.

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-10-22T21:23:09Z status=pass attempt=1 type=human

> **✅ gate:review_approved** run=2026-10-23T07:57:41Z status=pass attempt=1 type=human
