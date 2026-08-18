---
priority: medium
effort: low
depends: []
issue_type: bug
status: Implementing
labels: [bash_scripts, task_workflow]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
anchor: 1560
followup_kind: upstream_defect
created_at: 2026-08-18 23:44
updated_at: 2026-08-18 23:48
---

## Origin

Spawned from t1560_1 during Step 8b review.

## Upstream defect

- `.aitask-scripts/aitask_plan_externalize.sh` — `--no-worktree` did not clear the
  stale `Base branch:` / `Output branch:` frontmatter of an existing plan, though
  `.claude/skills/task-workflow/plan-externalization.md` documents that it does:
  "`--no-worktree` — when Step 5 worked on the current branch. Neither `base_branch`
  nor `output_branch` applies outside worktree mode, since nothing is cut and nothing
  is merged; **this also clears any stale `Base branch:` / `Output branch:` already
  present in a plan's frontmatter, so a later session cannot consume it.**"

## Reproduction

Observed on `aiplans/p1560/p1560_1_merge_mutex_and_broker_script.md`. The plan was
externalized with:

```bash
./.aitask-scripts/aitask_plan_externalize.sh 1560_1 \
  --internal <internal-plan> --force \
  --profile "aitasks/metadata/profiles/fast.yaml" --no-worktree
```

`fast.yaml` sets `create_worktree: false` and declares no `base_branch` /
`output_branch`. The helper returned `OVERWRITTEN:...` and the resulting header
still read:

```
Base branch: main
Output branch: main
```

Both fields pre-existed from an earlier externalization of the same plan.

## Why it matters

Those fields are not decorative. `task-workflow`'s **Re-entry Routing** resolves
both branches *from the plan header only* — deliberately never from the profile,
so that a resumed session under a different profile still lands where the original
did. Step 9 reads `Output branch:` the same way. A stale pair therefore survives
exactly the transition the clearing rule exists to prevent: a plan that once had a
worktree, re-planned on the current branch, still advertises a merge target a later
session will act on.

Impact on t1560_1 itself was nil (current-branch task, Step 9's merge block does not
run), which is why it was recorded rather than fixed there.

## Suggested fix

Check whether the per-field opt-in logic added for the "an invocation that supplies
no base never rewrites one" rule accidentally swallowed the `--no-worktree` clear
path — `--no-worktree` is documented as one of the three ways a call *does* claim
the base field, alongside `--base-branch[-file]` and a profile that sets
`base_branch`. Add a regression test that externalizes over a plan whose header
already carries both fields and asserts they are gone afterwards; the current suite
appears to cover only the write path, not the clear path.
