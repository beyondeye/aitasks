---
title: "Risk Evaluation"
linkTitle: "Risk Evaluation"
weight: 79
description: "Opt-in planning step that assesses code-health and goal-achievement risk, then offers before/after mitigation follow-ups"
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

From the identified risks, the agent proposes mitigation tasks under a `### Planned mitigations` block in the plan and confirms each one with you before anything is created. Mitigations come in two timings:

- **before** — an independent task that the original task **depends on**. When a "before" mitigation is created, the original is reverted to `Ready` (it shows as **Blocked** in `ait ls` until the mitigation lands) and the session ends. You implement the mitigation first, then re-pick the original.
- **after** — a post-implementation follow-up created once the original work is committed. It blocks nothing; the original task proceeds normally to archival.

Created mitigation tasks are recorded in the original's `risk_mitigation_tasks` frontmatter list. The proposal is always propose-and-confirm — no mitigation task is created without your approval.

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

## See Also

- [Follow-Up Tasks](../follow-up-tasks/) — the hub for all automatic follow-up flows
- [Plans](../../concepts/plans/) — where the `## Risk` section lives
- [Execution Profiles](../../skills/aitask-pick/execution-profiles/) — the `risk_evaluation` toggle
- [Task File Format](../../development/task-format/) — the `risk_code_health` / `risk_goal_achievement` / `risk_mitigation_tasks` fields
