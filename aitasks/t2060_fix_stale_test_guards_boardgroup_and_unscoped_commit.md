---
priority: medium
effort: low
depends: []
issue_type: bug
status: Implementing
labels: [git, bash_scripts, robustness]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
anchor: 1599
followup_kind: upstream_defect
implemented_with: claudecode/opus5_5
created_at: 2026-10-19 12:49
updated_at: 2026-10-19 17:00
---

## Origin

Spawned from t1739 during Step 8b review.

## Upstream defect

- `tests/test_aitask_merge_boardgroup.sh:200-205` — Test 3 greps `aitask_sync.sh` for `"$_MERGE_PYTHON" "$_MERGE_SCRIPT"` driver invocations, but the driver call moved to `lib/task_automerge.sh`, so "At least one driver invocation exists" fails on main independent of t1739.
- `tests/test_no_unscoped_task_commit.sh:679-680` — the scope assertion "markdown: the canonical teaching skill is in scope" (`.claude/skills/ait-git/SKILL.md` in the enumerated markdown sources) fails independent of t1739; root cause not investigated.

## Diagnostic context

t1739's regression sweep ran the 52 test files that touch the task-data git paths (`task_git`, `_task_pull_rebase`, `task_sync`, `task_push`, `./ait git`, `aitask_sync.sh`). 50 passed. These two failed on assertions unrelated to t1739's changed files: t1739 modified neither `aitask_sync.sh` nor anything under `.claude/skills/`.

- The boardgroup guard is a source-grep tripwire whose target moved. The t1727 extraction relocated the merge-driver invocation into `lib/task_automerge.sh`, so the guard now reads the wrong file and fails as "vacuous".
- The unscoped-commit scope check expects the `ait-git` skill source to be among the enumerated markdown instruction sources. Why it is missing (enumeration rule vs. a moved or renamed file) was not determined.

## Suggested fix

- Point Test 3 at every current driver call site (`lib/task_automerge.sh`, plus `aitask_sync.sh` if any remain), keeping its "not vacuous" floor.
- Inspect `md_sources_real` in `test_no_unscoped_task_commit.sh` against the current `.claude/skills/ait-git/` layout, and fix whichever side drifted.

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-10-19T14:00:01Z status=pass attempt=1 type=human
