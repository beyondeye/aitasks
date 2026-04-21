---
title: "Plans"
linkTitle: "Plans"
weight: 20
description: "The implementation contract written and approved before a task is coded."
depth: [main-concept]
---

## What it is

A **plan** is a markdown file in `aiplans/` named `p<N>_<short_name>.md` (mirroring its task: `aiplans/p130_add_login.md` corresponds to `aitasks/t130_add_login.md`). Child task plans live under `aiplans/p<parent>/p<parent>_<child>_<name>.md`. Each plan starts with a metadata header (the task it implements, the worktree, the branch, the base branch) and contains a context summary, a step-by-step implementation outline, the critical files to be touched, and verification steps. Plans are written during the planning phase of a skill like [`/aitask-pick`]({{< relref "/docs/skills/aitask-pick" >}}) and approved by the user before any code is written.

## Why it exists

A plan separates the **what** and **how** from the **doing**. The user approves the approach once, in plain English, and the agent then has a concrete contract to follow — and to update with deviations, post-review changes, and final implementation notes. Archived plans become the primary long-term record of how each task was actually built: subsequent sibling tasks read them as their main source of context, and the [Code Browser]({{< relref "/docs/tuis/codebrowser" >}}) surfaces them when explaining changed code. Externalizing the plan to `aiplans/` (rather than leaving it inside an agent's session memory) is what makes that long-term record possible.

## How to use

Plans are produced as a side effect of running [`/aitask-pick`]({{< relref "/docs/skills/aitask-pick" >}}) or [`/aitask-explore`]({{< relref "/docs/skills/aitask-explore" >}}) — you do not normally write the file by hand. The file naming, metadata header, and verification protocol are defined in the shared task-workflow skill — see [`task-workflow/planning.md`](https://github.com/dario-elyasy/aitasks/blob/main/.claude/skills/task-workflow/planning.md) on GitHub.

## See also

- [Tasks]({{< relref "/docs/concepts/tasks" >}}) — the work item a plan implements
- [Agent memory]({{< relref "/docs/concepts/agent-memory" >}}) — how archived plans become long-term context
- [Parent and child tasks]({{< relref "/docs/concepts/parent-child" >}}) — sibling plans share archived context
- [Verified scores]({{< relref "/docs/concepts/verified-scores" >}}) — plan verification feeds into per-model reliability tracking

---

**Next:** [Parent and child tasks]({{< relref "/docs/concepts/parent-child" >}})
