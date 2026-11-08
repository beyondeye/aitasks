---
title: "Premise Staleness Check"
linkTitle: "Premise Staleness"
weight: 62
description: "Advisory check, run when a task is picked, that reports whether the files its premise depends on changed since the premise was last known valid"
depth: [intermediate]
---

A task can sit `Ready` for months while the code it was written against moves underneath it. Its dependencies still resolve and its status is still honest, but its **premise** — the state of the code it describes — may no longer hold. The premise staleness check catches the detectable part of that drift: when you pick a task, it reports whether the files in the task's scope have changed since the premise was last known valid, and lets you decide what to do about it.

The check is **advisory**. It reports evidence — the commits and files involved — and never blocks a task on its own. It also makes a narrow claim: a clean result means "the watched files did not change", not "this task is still worth doing". Whether the work still makes sense is your call.

## When it runs

The check runs at the start of the shared task workflow, after a task is selected and **before** it is claimed. Every route into that workflow reaches it — [`/aitask-pick`]({{< relref "/docs/skills/aitask-pick" >}}), launching an agent on a task from the board, and [`/aitask-explore`]({{< relref "/docs/skills/aitask-explore" >}}) handing off to implementation.

It evaluates a task only when all of these hold:

- the task's status is `Ready`;
- the task is not a `manual_verification` task;
- the task carries a stored `premise_baseline` — the commit at which its premise was last known valid (see [Opting a task in](#opting-a-task-in));
- the task has a scope the check can derive: its `file_references` list, or, for a task with a `verifies` list, the files that the verified tasks' own commits touched.

Every other task is skipped **silently**. That includes every task without a stored baseline, a task whose scope is empty, and a task whose baseline commit is no longer in the repository's history (for example after a history rewrite). The check is also silent when every file in the scope was checked and none of them changed.

The fully autonomous [`/aitask-pickrem`]({{< relref "/docs/skills/aitask-pickrem" >}}) and [`/aitask-pickweb`]({{< relref "/docs/skills/aitask-pickweb" >}}) skills run their own workflow and do not include this check — see [Unattended runs](#unattended-runs).

## What it compares

The check compares the baseline commit with the current `HEAD`, path by path over the task's scope. It reads **committed history only**: uncommitted edits in your working tree are invisible to it.

The evidence it can report:

| Evidence | Meaning |
|---|---|
| **Changed** | Commits touched the file since the baseline. The prompt names how many, and which tasks made them. |
| **Deleted** | The file was removed since the baseline. The prompt names the task and commit that removed it. |
| **Added since the baseline** | The file did not exist at the baseline and does now (or was touched in between). |
| **Never existed** | The file exists neither at the baseline nor now, and no commit ever touched it — either a file the task intends to create, or a typo. The check cannot tell the two apart. |
| **Invalid reference** | A `file_references` entry that is not a usable path (for example an unquoted word YAML reads as something other than text). |
| **Could not be checked** | The history query for a path failed, or the origin of a `verifies` scope could not be read. |

The first three are **changes**. The last three are **unresolved scope or history**: they also trigger the prompt, even though no committed change was found, because an entry the check cannot confirm is never treated as an all-clear.

## The prompt and your four answers

When the check finds any of the evidence above, it asks one question, with the evidence inside the question itself (the first 10 rows are shown; the rest are summarised and still kept for a replan). Under an **interactive** execution profile on the shared workflow, this question is always asked when there is evidence — no interactive profile skips it, because the answer is what allows the baseline to move. (A non-interactive profile reports instead of asking, and the autonomous pick skills do not run the check — see [Unattended runs](#unattended-runs).)

| Answer | What happens | The baseline |
|---|---|---|
| **Proceed — premise still valid** | The task is claimed and the workflow continues as normal. | Advances to the commit that was checked. |
| **Review & replan with this evidence** | The task is claimed and planning starts with the evidence as input. If the task already has a plan, that plan is re-verified rather than reused as-is. The plan records a review of every evidence row. | Advances once the renewed plan is approved — including when you approve it and stop there. Unchanged if the plan is never approved. |
| **Postpone task** | The task is claimed, set to `Postponed`, and the session ends. To bring it back, run `ait update <id> --status Ready`. | Unchanged. |
| **Pick a different task** | Nothing is written; you go back to task selection. | Unchanged. |

A few details shape what these answers do:

- **The question is asked before the task is claimed; nothing is written until after.** Another session can claim a `Ready` task while the question is open, so the claim itself re-checks that the task is still `Ready`. If it changed meanwhile, nothing is claimed and you go back to task selection.
- **The baseline moves only to the commit you were shown.** Commits that land between the question and the write are not marked as reviewed; they surface at the next pick.
- **References to files that never existed get their own question.** After "Proceed", the workflow asks whether to keep or remove them from `file_references`. Keeping them is the default, since they may be files the task will create; a kept reference keeps being reported until the file exists or the reference is removed.
- **Unverifiable evidence blocks the advance.** If any path could not be checked, "Proceed" claims the task but leaves the baseline where it is, and the check runs again on the next pick — advancing would mark commits nobody saw as reviewed.
- **Invalid references cannot be cleared from the prompt.** They are reported until you fix the `file_references` entry by hand.

## Opting a task in

A task joins the check by carrying a `premise_baseline`. In most cases it gets one automatically:

- **At creation.** A task created with `--file-ref` or `--verifies` is stamped with the commit it was created at. This includes tasks created from the code browser, which passes `--file-ref` for the lines you selected (see [Creating Tasks from Code]({{< relref "/docs/workflows/create-tasks-from-code" >}})). A draft is stamped when it is finalized, not when it is written.
- **Carry-over tasks** created at archival inherit the original task's baseline instead of getting a new one, because the carried-over premise is as old as its source.

`--followup-of` does **not** opt a task in. It records only the topic anchor, which is not a scope the check can resolve.

To opt in an existing task, give it a scope and a baseline yourself. Adding a scope later never stamps a baseline on its own, so do both:

```bash
ait update 42 --file-ref lib/auth.py --file-ref lib/login.py
ait update 42 --premise-baseline "$(git rev-parse HEAD)"
```

The baseline must be a full commit id that exists in the repository; a bare id is stamped with the current time, and symbolic revisions such as `HEAD` are rejected — resolve them first, as above. See the [`premise_baseline` field]({{< relref "/docs/development/task-format" >}}) for the stored format.

## Opting a task out

Clear the field:

```bash
ait update 42 --premise-baseline ""
```

A task without a baseline is skipped silently from then on.

## Unattended runs

Two cases behave differently:

- **A non-interactive execution profile on the shared workflow** (such as `remote`) runs the check and, when there is evidence, displays it and continues. It never prompts, never advances the baseline and never postpones the task — each of those needs a person's confirmation — so the same evidence is shown again at the next attended pick.
- **The autonomous `/aitask-pickrem` and `/aitask-pickweb` skills** do not run the check at all.

## Limits

- **Tasks without a stored baseline are skipped.** There is no backfill: existing tasks join only when a baseline is set, at creation or by hand.
- **There is no time-based verdict.** Age alone never triggers the check; only evidence about the scope does.
- **It measures change, not behaviour.** A behaviour-preserving refactor of a scope file reads as a change, and a change elsewhere that invalidates the premise reads as clean.
- **An invalid reference keeps being reported** until the `file_references` entry is fixed by hand.
- **A kept reference to a file that never existed keeps being reported** until the file is created or the reference removed.
- **A session that cannot identify itself cannot advance the baseline.** The advance requires proof that this session holds the task's lock. A session running outside the agent's tmux pane without `AIT_AGENT_PID` cannot give that proof, so the baseline stays put and the question comes back on the next pick.
- **A draft is stamped when it is finalized.** A change that lands while a draft waits in `aitasks/new/` is not reported.

## Not the same as `verification_baseline`

`verification_baseline` is a separate field that belongs to [manual-verification]({{< relref "/docs/workflows/manual-verification" >}}) checklists: it records the commit a checklist is known to match. This check skips `manual_verification` tasks entirely and never reads that field.

## Related

- [Task Format]({{< relref "/docs/development/task-format" >}}) — the `premise_baseline` and `file_references` fields.
- [Creating Tasks from Code]({{< relref "/docs/workflows/create-tasks-from-code" >}}) — the most common way a task gets a scope and a baseline.
- [Manual Verification]({{< relref "/docs/workflows/manual-verification" >}}) — human-checked verification tasks, which this check skips.
- [`/aitask-pick`]({{< relref "/docs/skills/aitask-pick" >}}) — the workflow the check runs in.
- [Task management commands]({{< relref "/docs/commands/task-management" >}}) — `ait create` and `ait update` flags.
