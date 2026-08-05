---
title: "Risk Evaluation"
linkTitle: "Risk Evaluation"
weight: 79
description: "Opt-in planning step that assesses code-health and goal-achievement risk, then offers mitigations as spawned follow-up tasks or inline plan phases"
depth: [intermediate]
---

When you direct a coding agent, it is hard to know up front whether a planned change will hurt code stability, and whether the plan will actually deliver what you asked for. Risk evaluation adds a structured assessment at the **end of planning**: the agent rates two independent risk dimensions, records them in the plan, and can propose follow-up tasks that mitigate the risks before or after the work lands.

The feature is **opt-in and off by default**. It runs only when the active [execution profile](../../skills/aitask-pick/execution-profiles/) sets `risk_evaluation: true`; otherwise planning is unchanged.

## The Two Risk Dimensions

Risk is assessed as two separate `high`/`medium`/`low` levels — there is no single aggregate score:

- **Code-health risk** (`risk_code_health`) — stability, quality, maintainability, and blast-radius of the planned change.
- **Goal-achievement risk** (`risk_goal_achievement`) — whether the planned approach is sound and complete enough to actually deliver the requested goals (approach soundness, requirement coverage, feasibility).

A change can be low-risk on one dimension and high on the other — a small, well-isolated edit (low code-health risk) that may not fully solve the stated problem (high goal-achievement risk), for example. Keeping the dimensions separate makes that distinction explicit.

## The `## Risk` Plan Section

At the end of planning the agent appends a `## Risk` section to the [plan file](../../concepts/plans/), with one subsection per dimension headed by its level:

```markdown
## Risk

### Code-health risk: medium
- New shared helper touched by three call sites · severity: medium · → mitigation: t512

### Goal-achievement risk: low
- None identified.
```

Each bullet describes a specific risk, its severity, and — once mitigation is decided — a link to the task that addresses it.

After you approve the plan, the two decided levels are written to the task's `risk_code_health` and `risk_goal_achievement` frontmatter fields. They are display-only: they appear in [`ait board`](../../tuis/board/reference/#task-metadata-fields) (editable cycle fields, read-only once the task is Done or Folded) and in `ait ls` output, but they do not affect task sort order. See the [Task File Format](../../development/task-format/) reference for the field definitions.

## Risk-Mitigation Follow-ups

From the identified risks, the agent proposes mitigations under a `### Planned mitigations` block in the plan and confirms each one with you before anything is created. Each mitigation gets a **per-mitigation disposition** — spawn it as a separate task, or **inline it into the current plan as a pre-/post-phase**:

- **Spawn as "before" task** — an independent task that the original task **depends on**. When a "before" mitigation is created, the original is reverted to `Ready` (it shows as **Blocked** in `ait ls` until the mitigation lands) and the session ends. You implement the mitigation first, then re-pick the original.
- **Spawn as "after" task** — a post-implementation follow-up created once the original work is committed. It blocks nothing; the original task proceeds normally to archival.
- **Inline as pre-phase / post-phase** — the mitigation becomes an explicit, name-labeled step block in the plan itself (`### Pre-phase (risk mitigations)` before the implementation steps, `### Post-phase (risk mitigations)` after them). No task is created: the mitigation lands with the original work, in the same session.

Spawned mitigation tasks are recorded in the original's `risk_mitigation_tasks` frontmatter list; inline mitigations are not (there is nothing to track — they ship with the task, so the force re-verification below does not apply to them). The proposal is always propose-and-confirm — nothing is created or inlined without your approval.

### When to inline

Each proposed mitigation carries two agent-estimated decision metrics, and the agent derives a recommended disposition from them:

- `inline_risk` (`low`/`medium`/`high`) — the risk of incorporating the mitigation into the main task, estimated from separability: an independently-verifiable bounded addition (a characterization test, say) is low; work that could invalidate or reshape the plan (an approach spike) is high.
- `added_complexity` (`low`/`medium`/`high`) — how much the mitigation grows the task, relative to the plan's own scope.

Both metrics low → inline is recommended; any metric high → spawning is recommended; in between it is a judgement call, leaning spawn. You always decide — the recommendation only orders the options.

Inlining a small mitigation avoids a full extra task lifecycle and a forgettable Blocked task, and has a quality advantage: the shadow-agent review rounds (plan-challenge at planning, impl-challenge at implementation review) see the plan — so an inline phase gets that multi-round review coverage automatically, while a spawned mitigation task is invisible to it. When an inline mitigation is confirmed, the agent reassesses the augmented plan's risk levels once, so the recorded levels describe the plan you actually approve.

## Force Re-verification After a Mitigation Lands

A "before" mitigation changes the codebase underneath the original task's plan. To prevent reusing a now-stale plan, when a listed mitigation task is archived after the plan's most recent verification, the original's plan is **force re-verified on the next pick** — even under a profile that would normally reuse the existing plan. This keeps the plan honest about the code it was written against.

## Enabling Risk Evaluation

Set `risk_evaluation: true` in an execution profile (or via the [Settings TUI](../../tuis/settings/) → Profiles tab → Planning group):

```yaml
# aitasks/metadata/profiles/myprofile.yaml
name: myprofile
description: Like fast, with risk evaluation enabled
risk_evaluation: true
```

With the key omitted or `false`, none of the above runs and planning behaves exactly as before. See [Execution Profiles](../../skills/aitask-pick/execution-profiles/) for the full key reference.

## The `risk_evaluated` Gate

A task can also *require* that this step happened, by declaring the
`risk_evaluated` [gate](../../commands/gates/). The gate is verified by
[`ait gates run`](../../commands/gates/#ait-gates-run), which checks that the
plan carries a `## Risk` section and that the task's two risk levels are set —
so a risk-gated task cannot archive with the evaluation skipped.

If the gate reports `blocked: no verifier configured (deferred)`, or picking the
task warns that `risk_evaluated` has no verifier, the project's gate registry is
missing the entry that tells the framework how to check it. Run
[`ait gates sync-registry`](../../commands/gates/#ait-gates-sync-registry) to
reconcile it.

## See Also

- [Follow-Up Tasks](../follow-up-tasks/) — the hub for all automatic follow-up flows
- [Gates](../../commands/gates/) — the `risk_evaluated` gate that verifies this step's output
- [Plans](../../concepts/plans/) — where the `## Risk` section lives
- [Execution Profiles](../../skills/aitask-pick/execution-profiles/) — the `risk_evaluation` toggle
- [Task File Format](../../development/task-format/) — the `risk_code_health` / `risk_goal_achievement` / `risk_mitigation_tasks` fields
