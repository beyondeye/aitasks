---
priority: medium
risk_code_health: low
risk_goal_achievement: low
effort: medium
depends: []
issue_type: test
status: Implementing
labels: [git, bash_scripts, robustness, tests]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
anchor: 1658
followup_kind: risk_mitigation
implemented_with: claudecode/opus5
created_at: 2026-09-01 18:55
updated_at: 2026-09-02 16:23
---

## Origin

Risk-mitigation ("after") follow-up for t1658_2, created at Step 8d after implementation landed.

## Risk addressed

From `aiplans/archived/p1658/p1658_2_*.md` `## Risk` → code-health:

> The nested-repository boundary (a submodule or any nested checkout must
> resolve to its **own** legacy mode, never the parent's data worktree) is
> preserved by a source comment alone — no test exercises a nested repository
> today. A later change to rung 2 or rung 3 could therefore make a nested
> checkout silently operate on its parent's data branch, which is the same
> silent-wrong-target class this task exists to remove.

## Goal

`_ait_detect_data_worktree()` in `.aitask-scripts/lib/task_utils.sh` resolves the
data worktree through a four-rung ladder (t1658_2). Rungs 2 and 3 derive an
absolute `<root>/.aitask-data` from `git rev-parse --show-toplevel` and from
`ait_main_worktree_root()` respectively, and both stop at a repository boundary —
so a submodule, or any nested checkout, resolves to its **own** root and
therefore to legacy mode, never the parent repo's data branch. That is
`ait_main_worktree_root()`'s documented same-repo property and is the correct
answer.

Today that boundary is held by a **source comment only**. Add a regression test
so a later change to rung 2 or rung 3 cannot silently move a nested checkout onto
its parent's data branch.

### What to add

In `tests/test_task_git.sh`, alongside the existing Test 13 (cwd shapes) and
Test 14 (indeterminate-topology refusal), add a nested-repository case:

- A **branch-mode** parent checkout that really has `.aitask-data` (build it the
  way Test 13 does: `setup_repo_with_remote` + `setup_data_branch`).
- An **inner** checkout nested inside it that is its own git repository and has
  no `.aitask-data` of its own. Cover the plain nested-repo shape; a real
  `git submodule add` variant is worth adding too if it can be built without a
  network round-trip.
- Assert that `_ait_detect_data_worktree` answers `"."` from inside the inner
  repository, **and** that the resolved value does not name the parent's data
  worktree — the second half is what makes it a boundary test rather than a
  restatement of the first.

### Notes

- Follow the file's existing style: probe with a cold cache
  (`_AIT_DATA_WORKTREE=""`) via a `pushd`/`popd` helper, and use
  `assert_eq_trim`. Test bodies run at top level, not in `( … )` subshells — keep
  it that way, or opt into the file-backed counters per CLAUDE.md.
- Make it falsifiable: confirm the assertion fails if rung 2/3 are relaxed to
  walk past a repository boundary. A test that cannot fail adds nothing.
- Do **not** change `_ait_detect_data_worktree()` itself — the boundary is
  already correct by construction; this task only pins it.

## Verification

```bash
bash tests/test_task_git.sh
shellcheck tests/test_task_git.sh
```

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-09-02T13:23:21Z status=pass attempt=1 type=human

> **✅ gate:review_approved** run=2026-09-02T13:42:37Z status=pass attempt=1 type=human
