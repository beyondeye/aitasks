---
title: "Gates"
linkTitle: "Gates"
weight: 85
description: "Named checks a task must satisfy before it archives: what a task asks for, what the framework enforces, and what to do when a gate fails."
depth: [intermediate]
---

## What it is

A **gate** is a named check a task must satisfy before it can be archived: a
build that must pass, a test suite that must be green, a risk evaluation that
must have been done, or a review a person must sign off. A task's gates are
recorded apart from its `status` field, and they come into play only while the
task is `Implementing`: they are checked as the work proceeds and when the task
archives, and a task archives only once every gate its workflow enforces is satisfied, unless you explicitly override that check.

## Why it exists

A single `status` field cannot say "the build passed, the review is pending and
the docs still need updating". Those are independent facts that finish at
different times. Gates hold them separately, in the task file, where they
survive a crashed session and are visible from every machine that syncs the
task data. Some gates also hold back the tasks that depend on this one until
they pass.

A task declares the gates it asks for, and the
[execution profile]({{< relref "/docs/concepts/execution-profiles" >}}) you pick
it under decides which of them its workflow enforces. The same task can be
picked under different profiles, and each enforces only the gates its workflow
can check. The enforced gates are fixed when you pick the task (see
[Task lifecycle]({{< relref "/docs/concepts/task-lifecycle" >}})) and stay the
same until it is picked again.

## How to use

Declare gates when you create a task, with the batch `--gates` flag described on
the [`/aitask-create`]({{< relref "/docs/skills/aitask-create" >}}) page, or let
an execution profile's `default_gates` declare them for you. The rest is the
framework's job: the enforced gates are worked out when you pick the task, each
gate's result is recorded as the workflow reaches it, and archival waits for
them.

To act on gates directly, use [`ait gates` and `ait gate`]({{< relref "/docs/commands/gates" >}}):
run them, list their state, sign a human gate, read a run's log.
[`/aitask-run-gates`]({{< relref "/docs/skills/aitask-run-gates" >}}) runs the
machine gates that are ready, the ones a script checks, and explains the
result; the board shows each in-flight task's gates against its enforced set.

When a gate fails, the failure is recorded in the task file and the task stays
active. `ait gate log <task> <gate>` shows why. After you fix the cause, a gate
that a script checks runs again with `ait gates run <task> --gate <gate>`, even
when its retries are spent. A gate whose check is work a coding
agent does, such as `docs_updated` (updating the documentation), cannot be run
that way. The coding agent runs it again when the task next reaches review or
archival, so carry on with the task in your coding agent, or pick it again with
[`/aitask-pick <id>`]({{< relref "/docs/skills/aitask-pick" >}}). When a gate cannot pass because the registry never says how to check it, run [`ait gates sync-registry`]({{< relref "/docs/commands/gates" >}}#when-to-run-sync-registry). A human gate such as `review_approved` waits for a person: it is recorded when you approve the review in an attended session, or the reviewer signs it later with `ait gate pass <task> <gate>`. An agent never approves it on its own.
Archiving with an unmet gate needs an explicit override; see
[Gate rules]({{< relref "/docs/development/gates" >}}#archival).

## See also

- [Gate rules]({{< relref "/docs/development/gates" >}}): how the enforced set is derived and stored, the kinds of gate, the ledger, the registry, retries, the unlock order, archival and dependents.
- [`ait gates` and `ait gate`]({{< relref "/docs/commands/gates" >}}): the command reference for running, listing, signing off and reconciling the registry.
- [`/aitask-run-gates`]({{< relref "/docs/skills/aitask-run-gates" >}}): the conversational front of the gate engine.
- [`/aitask-gate-docs-updated`]({{< relref "/docs/skills/aitask-gate-docs-updated" >}}#why-it-runs-where-it-runs): the procedure-backed gate, and why only an attended agent can run it.
- [Task file format]({{< relref "/docs/development/task-format" >}}#frontmatter-fields): the `gates`, `also_blocks_dependents` and `active_gates*` field rows.
- [Board reference]({{< relref "/docs/tuis/board/reference" >}}#gate-progress): how the board counts satisfied gates against the enforced set.
- [Risk evaluation]({{< relref "/docs/workflows/risk-evaluation" >}}): the planning step the `risk_evaluated` gate verifies.
- [Execution profiles]({{< relref "/docs/concepts/execution-profiles" >}}): what a profile is; each one also limits which gates its workflow enforces.
- [Task lifecycle]({{< relref "/docs/concepts/task-lifecycle" >}}): picking, implementing and archiving a task.

---

**Next:** [Locks]({{< relref "/docs/concepts/locks" >}})
