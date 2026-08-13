---
title: "/aitask-run-gates"
linkTitle: "/aitask-run-gates"
weight: 16
description: "Run a task's declared gates — the conversational front of the gate orchestrator"
maturity: [experimental]
depth: [advanced]
---

`/aitask-run-gates <task-id>` runs a task's declared [gates]({{< relref "/docs/commands/gates" >}}) and explains the result in prose. It is the **conversational front** of the same orchestrator engine that [`ait gates run`]({{< relref "/docs/commands/gates" >}}#ait-gates-run) drives — it never reimplements the decision logic, so the CLI and the skill can never disagree about what should run.

Reach for the skill when you want the outcome interpreted — which gate is blocking, what the next action is, whether the task is ready to archive. Reach for the CLI when you want the raw result.

**Usage:**
```
/aitask-run-gates 42                          # Run every unlocked gate
/aitask-run-gates 42_2                        # Child task
/aitask-run-gates 42 --gate risk_evaluated    # Force-run a single gate
/aitask-run-gates 42 --dry-run                # Report the plan; run nothing
```

A task ID is **required** — a parent (`42`) or a child (`42_2`).

> **Note:** Must be run from the project root directory. See
> [Skills overview](..) for details.

## Arguments

| Argument | Effect |
|----------|--------|
| `--gate <name>` | Run one named gate, even if it already passed and even if its retry budget is spent. Its predecessors must still be satisfied. Parallel fan-out is skipped. |
| `--dry-run` | Report the decision tree — what would run, what is locked, what is exhausted — without invoking a verifier or writing to the ledger. |

## What it reports

- **All gates satisfied** — it says so and *suggests* archiving. It never sets `status: Done` itself.
- **A human gate is pending** — it explains the action a person now has to take. It **never creates the sign-off signal on your behalf**; an agent signing a human gate would defeat the point of having one.
- **Retries exhausted** — it points you at [`ait gate log`]({{< relref "/docs/commands/gates" >}}#ait-gate-log) for the failure history.
- **A verifier errored or the registry is malformed** — it surfaces the problem rather than treating it as a failed gate.

## What it will not do

The skill is advisory and orchestration only. It does not edit task frontmatter, merge branches, or archive tasks — those belong to the task workflow. Gates whose verifier is a *procedure* an agent must carry out (such as `docs_updated`) are not run here either: the orchestrator reports them as needing an agent, and the attended workflow runs them at review time. See [`/aitask-gate-docs-updated`](../aitask-gate-docs-updated/).

## Related

- [Gates CLI reference]({{< relref "/docs/commands/gates" >}}) — `ait gates run`, `ait gate pass`, `ait gate log`
- [`/aitask-resume`](../aitask-resume/) — re-enter an in-flight task at its first unmet checkpoint
