---
priority: medium
risk_code_health: low
risk_goal_achievement: low
effort: low
depends: []
issue_type: bug
status: Implementing
labels: [task_workflow]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
anchor: 1468
followup_kind: upstream_defect
implemented_with: claudecode/opus5
created_at: 2026-08-11 14:30
updated_at: 2026-08-11 17:11
---

## Origin

Spawned from t1468_2 during Step 8b review.

## Upstream defect

- `tests/golden/procs/task-workflow/SKILL-default.md:1 — the three SKILL-*.md
  goldens are stale at HEAD: commit 4f8d0387e (t1466) edited
  .claude/skills/task-workflow/SKILL.md without regenerating them (goldens last
  updated in 4ba78d1c7, t1272), so tests/test_skill_render_task_workflow.sh has
  3 failing golden diffs independent of any current work.`

## Diagnostic context

t1468_2 added `task-creation-batch.md` to `WRAPPED_FILES_VARYING` in
`tests/test_skill_render_task_workflow.sh` and regenerated the affected goldens.
Running the suite then showed 3 failures — `golden SKILL × {default,fast,remote}`
— which at first looked caused by that change.

They are not. Proven two ways:

1. `.claude/skills/task-workflow/SKILL.md` in the working tree was **byte-identical
   to HEAD** (`diff` against `git show HEAD:...` was empty) — t1468_2 never touched
   that file.
2. Rendering **HEAD's own copy** of `SKILL.md` against
   `aitasks/metadata/profiles/default.yaml` still differs from the committed
   golden, so the staleness exists at HEAD independently of any working-tree
   change.

`git log` confirms the provenance: the source last changed in `4f8d0387e`
(t1466, "Gate lock acquisition on holder liveness") while the goldens last
changed in `4ba78d1c7` (t1272). The diff is exactly t1466's content — the new
`LOCK_LIVE_HOLDER:` / `LOCK_UNVERIFIABLE_HOLDER:` branches in Step 4, the
expanded `RECLAIM_STATUS:` description, and the matching Step-7 guard bullet.

t1468_2 initially regenerated the three files to get a green suite, but that was
reverted on review: curing a pre-existing regression fixture inside an unrelated
task obscures provenance. Hence this task.

This is a repeat of a known failure mode — CLAUDE.md and
`aidocs/framework/skill_authoring_conventions.md:467` both require goldens to be
regenerated in the **same commit** as the template/procedure edit.

## Scope amendment (during implementation)

A **fourth** stale golden was found while verifying that no others had drifted:
`tests/golden/skills/aitask-pickrem/SKILL-remote-claude.md` (last regenerated in
`b9c44161b`, t1233). Same root cause, same commit — `4f8d0387e` (t1466) also
edited `.claude/skills/aitask-pickrem/SKILL.md.j2` without regenerating it,
leaving `tests/test_skill_render_aitask_pickrem.sh` red at 66/67. The user
confirmed it is in scope, so this task cures **four** goldens, not three; the
fix below is amended accordingly.

All other goldens are current: every `tests/test_skill_render_*.sh` was run,
covering all 76 files under `tests/golden/`.

## Suggested fix

Regenerate the four goldens with the documented loop
(`aidocs/framework/skill_authoring_conventions.md:484-497`). Note the two sources
differ in kind and in golden dimensionality: `task-workflow/SKILL.md` is a
**wrapped `.md`** whose goldens live under `tests/golden/procs/` with no
`-claude` suffix, across 3 profiles; pickrem is a **`.j2`** with a single
`remote` × `claude` golden (see `tests/test_skill_render_aitask_pickrem.sh:5`).

```bash
PYTHON="$(source .aitask-scripts/lib/python_resolve.sh && require_ait_python)"
for profile in default fast remote; do
  "$PYTHON" .aitask-scripts/lib/skill_template.py \
    .claude/skills/task-workflow/SKILL.md \
    aitasks/metadata/profiles/$profile.yaml claude \
    > tests/golden/procs/task-workflow/SKILL-${profile}.md
done

"$PYTHON" .aitask-scripts/lib/skill_template.py \
  .claude/skills/aitask-pickrem/SKILL.md.j2 \
  aitasks/metadata/profiles/remote.yaml claude \
  > tests/golden/skills/aitask-pickrem/SKILL-remote-claude.md
```

Then confirm both suites are fully green — `bash
tests/test_skill_render_task_workflow.sh` (184/184) and `bash
tests/test_skill_render_aitask_pickrem.sh` (67/67). Review the diff before
committing to confirm it contains only t1466's intended content and no unrelated
drift.

Worth considering as part of the fix: nothing mechanically enforces the
same-commit rule, which is why this drifted silently for two tasks. A pre-commit
check or a CI step that fails when a wrapped source file is newer than its
golden would close the loop. **Deferred by the user to t1484** (`enforce skill
golden freshness`), which records the design constraints found here — chiefly
that `aitask_skill_verify.sh` does not inspect goldens at all, that no single
place knows the golden matrix, and that CLAUDE.md's `.j2`/stub-surface trigger
would not have fired on t1466's wrapped-`.md` edit anyway.

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-08-11T14:11:36Z status=pass attempt=1 type=human
