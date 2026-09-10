---
priority: medium
effort: medium
depends: []
issue_type: bug
status: Ready
labels: [gates, task_workflow]
gates: [risk_evaluated]
anchor: 635
followup_kind: upstream_defect
created_at: 2026-09-10 11:58
updated_at: 2026-09-10 11:58
---

## Origin

Found while implementing t1772 under the `fast` profile (current-branch mode).
Not caused by t1772: this is an existing gap in the task-workflow skill.

## Problem

In current-branch mode, nothing records `risk_evaluated` before archival. So a
task with that gate reaches `aitask_archive.sh` with the gate still pending, and
the archive script refuses.

- Step 7 (`.claude/skills/task-workflow/SKILL.md:583`) runs
  `aitask_gate.sh should-self-record <task_id> risk_evaluated`. When the gate is
  in the task's active set this exits 1 and Step 7 skips recording it, on the
  premise that "the Step-9 orchestrator records it".
- Step 9 calls the orchestrator (`ait gates run <task_id>`) in exactly one
  place, the "Verify implementation" block at `SKILL.md:884`. That block sits
  under `**If a separate branch was created:**` (`SKILL.md:835`). A
  current-branch task skips the whole block and goes straight to "Run the
  archive script" (`SKILL.md:942`).
- So `risk_evaluated` is never recorded, `archive-ready` reports
  `BLOCKED:risk_evaluated`, and `aitask_archive.sh` exits 2 with
  `GATE_PENDING:risk_evaluated`.

Line numbers are as of `2c255e228`.

**Blast radius (read from the skill text, not yet measured across real
picks):** the shipped `fast` profile sets `create_worktree: false`,
`record_gates: true` and `default_gates: [risk_evaluated]`. So every `fast`
pick of a task that declares the gate is affected. The failure is **not
silent**: the archive script catches it and asks "Resolve now & archive" or
"Defer". But that adds a confusing stop at the end of the default path. And
"Resolve now" invites hand-writing a pass for a machine gate, when its verifier
should run instead.

## Evidence (t1772, 2026-09-10)

- After Step 8, `./.aitask-scripts/aitask_gate.sh status 1772` listed only
  `plan_approved` and `review_approved`, and `archive-ready 1772` printed
  `BLOCKED:risk_evaluated`.
- Running `./ait gates run 1772` by hand recorded `risk_evaluated: pass`. Then
  `archive-ready` printed `ALL_PASS` and `aitask_archive.sh 1772` archived
  cleanly (`5bca7dd75`).

## How it formed

Two changes, each reasonable on its own:

- **t635_12** (`32af7f00e`) made Step 9's "Verify implementation" call
  `ait gates run`, inside the existing separate-branch block.
- **t635_14** made the orchestrator record `risk_evaluated` whenever the gate
  is in the active set (the Step 7 `should-self-record` handoff).

Keeping this block branch-only was a deliberate choice, but for *other* gates.
The t635_2 plan
(`aiplans/archived/p635/p635_2_task_workflow_checkpoint_recording.md:115-120`)
says that under `fast`, `build_verified` and `merge_approved` only run when a
separate branch was created. That choice predates `risk_evaluated`'s recording
moving into the same block. The t1560_2 plan
(`aiplans/archived/p1560/p1560_2_wire_step9_across_rendered_surfaces.md:530`)
noticed that `fast` never runs the block, but only as a gap in testing its
merge rewrite.

## Suggested direction (not prescriptive)

- Give the current-branch path its own gate run before "Run the archive
  script". Dispatch `./ait gates run <task_id>` with the same capture block and
  status handling, but without the merge mutex, since nothing is merged. Or
  move the orchestrator call out of the separate-branch block and keep only the
  merge-related parts inside it.
- Decide explicitly whether `build_verified` should now run on current-branch
  picks, since t635_2 chose not to. Either keep that exclusion and say why in
  the skill text, or remove it. Don't change it by accident.
- The autonomous lanes already run `ait gates run` on the current branch
  (t635_17), which gives a working model for the call.

## Files

- `.claude/skills/task-workflow/SKILL.md`: the Step 7 handoff text (~583) and
  Step 9 (~831-942).
- `.claude/skills/task-workflow/merge-broker.md`: also carries the
  separate-branch wording. Check whether its "Return to Step 9 — Verify
  implementation" contract has to change.
- The rendered copies are regenerated, never hand-edited:
  `.claude/skills/task-workflow-{default,fast,remote}-/`,
  `.agents/skills/task-workflow-*-codex-/`, `.opencode/skills/task-workflow-*-/`.
- Goldens: `tests/golden/procs/task-workflow/SKILL-{default,fast,remote}.md`
  and `tests/golden/procs/task-workflow/merge-broker-default.md`. Run
  `./.aitask-scripts/aitask_skill_verify.sh` and regenerate the goldens in the
  same commit (see `aidocs/framework/skill_authoring_conventions.md`).

## Coordination

- **t635_24** (remove the legacy `verify_build` path) rewrites the same "Verify
  implementation" region, and t635_25 already routes its gate-run extraction
  there. Do this fix together with t635_24 or straight after it, so Step 9 is
  not re-rendered twice. There is deliberately no hard dependency: this fix is
  correct on its own, and nobody has picked up t635_24.
- **t1166_3** (family worktree mode) splits the same `If a separate branch was
  created` block into family-child and per-task paths. Whichever of the two
  lands second must keep the current-branch gate run reachable.

## Related

- t635_17: gate strictness in the autonomous lanes (pickrem/pickweb run
  `ait gates run`).
- t1417: wording of the archive refusal for stale-signature gates. It is the
  same `GATE_PENDING` message this gap currently triggers.
- t1772: where this was found (archived).

## Acceptance criteria

- A task with `risk_evaluated`, picked under a current-branch profile, reaches
  `archive-ready` = `ALL_PASS` through the workflow alone: no hand-run
  `ait gates run`, and no archive-script prompt.
- Picks that use a worktree or separate branch are unchanged: the gate run
  still happens under the merge mutex, with the merge reservation held.
- The skill text states whether `build_verified` runs on current-branch picks.
- A check that fails against today's text proves the fix, e.g. an assertion
  that the rendered `SKILL-fast.md` golden reaches a gate-run call on the
  current-branch path. A regenerated golden alone cannot prove the content is
  present.
- `aitask_skill_verify.sh` passes, and the goldens are regenerated in the same
  commit.
