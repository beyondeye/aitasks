---
title: "/aitask-gate-docs-updated"
linkTitle: "/aitask-gate-docs-updated"
weight: 17
description: "The verifier for the docs_updated gate — updates the project's documentation, with your confirmation, and records the result"
maturity: [experimental]
depth: [advanced]
---

`/aitask-gate-docs-updated` is the verifier for the **`docs_updated`** gate. Where most gates check something that is already true, this one verifies *work an agent has to do*: it inspects what a task changed, proposes the documentation updates that change implies, applies them once you confirm, and records the gate result.

**Usage:**
```
/aitask-gate-docs-updated <task-id> <attempt> <run-id>
```

All three arguments are **required** and are allocated by the workflow, not typed by hand — you normally never invoke this skill directly. It is dispatched automatically during task review.

> **Note:** Must be run from the project root directory. See
> [Skills overview](..) for details.

## Why it runs where it runs

`docs_updated` is a **procedure-backed** gate. The headless gate orchestrator cannot satisfy it — running it means writing documentation — so [`ait gates run`]({{< relref "/docs/commands/gates" >}}#ait-gates-run) reports it as needing an agent and defers.

Instead it runs from the **attended** workflow, at review time and *before* the change summary you approve. That timing is deliberate: the doc edits become part of the diff you review, and they land in the same commit as the code they describe, rather than trailing it.

## How it decides what your task changed

Before it can propose anything, the skill has to know which files belong to *this* task. On a busy checkout that is not the same question as "what is currently modified" — your working tree may also hold another task's work in progress, or edits made by a session running alongside yours. Documenting someone else's change is worse than documenting nothing, so the skill does not treat the whole modified tree as yours.

It attributes each file from three signals:

- files already **committed under this task's tag** — proof they are yours;
- files this task's **implementation plan names by exact path** — your declared scope;
- files that were **already modified when you picked the task** — proof they belong to other work, and excluded.

A file matching none of those — one that appeared after you picked the task and that your plan does not name — cannot be assigned either way. The skill lists those and **asks you** whether they are part of this change before it infers anything from them. Autonomous execution profiles, which have nobody to ask, leave them out and record the exclusion in the gate's log.

Naming a *directory* in your plan does not claim the files inside it; only exact file paths count. That keeps a plan that mentions, say, a source or test directory in passing from silently claiming everything under it.

## How it decides what to write

The skill does not carry its own idea of how your project documents things. It reads the project's configured doc-update guide, resolved through the standard configuration path (defaulting to `aitasks/metadata/doc_update_guide.md`), and follows that guide's map from *kind of change* to *area of documentation*.

It then proposes the specific updates and asks you before touching anything: apply them, adjust them, mark them not needed, or reject them. Autonomous execution profiles follow their configured policy instead of blocking on the question.

## Results

| Result | Meaning |
|--------|---------|
| `pass` | The docs were updated — or confirmed already correct |
| `skip` | The change has no documentation-relevant surface |
| `fail` | Documentation was needed and you declined to add it |

A `fail` is not fatal to the session, but it leaves the gate unsatisfied, and an unsatisfied gate blocks archival until it is resolved.

## Availability

This skill is available in Claude Code and all other supported coding agents.

## Related

- [Gates CLI reference]({{< relref "/docs/commands/gates" >}}) — inspecting and signing off gates
- [`/aitask-run-gates`](../aitask-run-gates/) — run a task's other gates
