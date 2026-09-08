---
priority: medium
risk_code_health: low
risk_goal_achievement: medium
effort: low
depends: []
issue_type: bug
status: Implementing
labels: [git, bash_scripts, robustness]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 4a36c12bb96d.681bafac2cb9.d73bba2fc21f
risk_mitigation_tasks: [1747]
assigned_to: dario-e@beyond-eye.com
implemented_with: claudecode/opus5
created_at: 2026-09-07 18:40
updated_at: 2026-09-08 18:35
---

## Defect

`_fold_amend_guard` in `.aitask-scripts/aitask_fold_mark.sh` decides whether HEAD
is the fold's own commit before rewriting it with `commit --amend`. It reads
HEAD's path list like this (`:916`):

```bash
done < <(task_git show --name-only --format='' HEAD 2>/dev/null || true)
```

That **fails open** in two ways, and both permit the amend rather than refusing:

1. **A failed probe reads as "nothing foreign".** If `task_git show` exits
   non-zero the `|| true` hands back an empty list, the `foreign` array stays
   empty, and the guard returns 0 — authorising a history rewrite of a commit
   whose contents were never read.
2. **An empty path list is not evidence of safety.** `git show --name-only`
   prints no file list for a **merge commit**, so a merge HEAD also yields an
   empty list and is likewise approved for amending.

This inverts the function's own stated contract. Its header says it is
DEFAULT-DENY with "deliberately no warn-and-proceed bucket" — but an
unreadable HEAD is currently the widest proceed-anyway path in it.

## Precedent for the fix

`lib/task_utils.sh::task_git_commit_scoped` already states the rule this should
follow: capture the probe's exit status separately so a failing probe reads as
*unverified*, never as *clean*.

t1599_4 hit the identical shape in the guard it added to
`aitask_issue_import.sh` and closed it there:

```bash
local head_paths="" show_rc=0
head_paths="$(task_git show --name-only --format='' HEAD 2>/dev/null)" || show_rc=$?
(( show_rc != 0 )) && refuse "...unverified..."
[[ -z "${head_paths//[[:space:]]/}" ]] && refuse "...no paths (empty or merge commit)..."
```

t1599_4 did **not** apply it here: `aitask_fold_mark.sh` is t1599_2's file and
that child's task explicitly forbids cross-boundary edits.

## Verification

Mirror the controls already written for the issue-import guard in
`tests/test_issue_import_amend_guard.sh` (A6a / A6b), adapted to
`tests/test_fold_mark.sh`:

- **Unreadable HEAD** (e.g. an unborn/orphan branch) must **refuse**, not amend.
- **Merge HEAD** must refuse: build a real merge commit, confirm its
  `--name-only` output is empty, and assert the merge is NOT rewritten.
- **Negative control (required):** both assertions must FAIL against the current
  `|| true` shape. Verified reachable — the equivalent control on the
  issue-import guard rewrote the merge commit before the fix.
- The existing permit-direction tests (7 and 11 in `test_fold_mark.sh`) must keep
  passing, so the tightening does not start refusing legitimate folds.

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-09-08T15:10:55Z status=pass attempt=1 type=human

> **✅ gate:review_approved** run=2026-09-08T15:32:29Z status=pass attempt=1 type=human
