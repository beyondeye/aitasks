---
title: "Premise Staleness Check"
linkTitle: "Premise Staleness"
weight: 62
description: "Advisory check, run when a task is picked, that reports whether the files its premise depends on changed since the premise was last known valid"
depth: [intermediate]
---

A task can wait in `Ready` for months while the code it describes changes. Its dependencies still resolve and its status stays accurate, so neither shows that drift. Its **premise** is the state of the code it was written against. When you pick the task, the premise staleness check tells you which files in the task's scope changed since its premise was last known valid, and you decide whether the work still makes sense. The check is advisory: it shows the commits and files involved and never blocks a task on its own. A clean result means only that the files in its scope did not change.

## When you see the prompt

The check runs before the task is claimed, whether you pick it with [`/aitask-pick`]({{< relref "/docs/skills/aitask-pick" >}}), launch it from the board, or hand it to implementation from [`/aitask-explore`]({{< relref "/docs/skills/aitask-explore" >}}). It asks a question only when all of these hold:

- the task is `Ready` and is not a `manual_verification` task;
- the task has a premise baseline, the commit at which its premise was last known valid (see [Opting a task in](#opting-a-task-in));
- the task has a scope: its `file_references` list or, for a task with a `verifies` list, the files the verified tasks changed;
- the check finds evidence in that scope: a file changed, was deleted or was added since the baseline, a file could not be checked, a reference names a file that never existed, or a `file_references` entry is not a usable path.

In every other case the check says nothing. It reads committed history only, so uncommitted edits in your working tree do not count. The [premise staleness rules]({{< relref "/docs/development/premise-staleness" >}}#evidence) list every kind of evidence the prompt can show.

## Answering the prompt

The question carries the evidence and offers four answers:

- **Proceed — premise still valid**: the task is claimed and work continues. The baseline moves to the commit you were shown, so these changes are not reported again. If the evidence lists files that never existed, you are then asked whether to keep those references, since they may be files the task will create, or remove them.
- **Review & replan with this evidence**: the task is claimed and planning starts from the evidence, re-checking any plan the task already has. The baseline moves once you approve the renewed plan.
- **Postpone task**: the task is claimed, set to `Postponed`, and the session ends. Bring it back with `ait update --batch <id> --status Ready`.
- **Pick a different task**: nothing changes, and you go back to task selection.

Some evidence keeps the baseline where it is even after "Proceed". A file whose history could not be read is one case; the check then asks again at the next pick. The [rules that shape the answers]({{< relref "/docs/development/premise-staleness" >}}#rules-that-shape-the-answers) list every such case.

## Opting a task in

A task joins the check by carrying a `premise_baseline`. A task created with `--file-ref` or `--verifies` gets one automatically: it is stamped with the commit it was created at. This includes tasks created from the code browser, which passes `--file-ref` for the lines you selected (see [Creating Tasks from Code]({{< relref "/docs/workflows/create-tasks-from-code" >}})). A draft is stamped when it is finalized, not when it is written.

`--followup-of` alone does not opt a task in. It records only the [topic anchor]({{< relref "/docs/concepts/topic-anchoring" >}}), which gives the check no files to compare.

To opt in an existing task, give it a scope and a baseline yourself. Adding a scope later never sets a baseline on its own, so do both:

```bash
ait update --batch 42 --file-ref lib/auth.py --file-ref lib/login.py
ait update --batch 42 --premise-baseline "$(git rev-parse HEAD)"
```

The baseline must be a full commit id that exists in the repository. Symbolic revisions such as `HEAD` are rejected, so resolve them first, as above. An id given without a time is stored with the current time; see the [`premise_baseline` field]({{< relref "/docs/development/task-format" >}}#frontmatter-fields) for the stored format.

## Opting a task out

Clear the field:

```bash
ait update --batch 42 --premise-baseline ""
```

A task without a baseline is skipped silently from then on.

## Unattended runs

A non-interactive execution profile such as `remote` shows the evidence and continues without asking, so the baseline stays put until an attended pick. The autonomous [`/aitask-pickrem`]({{< relref "/docs/skills/aitask-pickrem" >}}) and [`/aitask-pickweb`]({{< relref "/docs/skills/aitask-pickweb" >}}) skills do not run the check at all ([details]({{< relref "/docs/development/premise-staleness" >}}#unattended-runs)).

## Not the same as `verification_baseline`

`verification_baseline` is a separate field that belongs to [manual-verification]({{< relref "/docs/workflows/manual-verification" >}}) checklists: it records the commit a checklist is known to match. This check skips `manual_verification` tasks entirely and never reads that field.

## Related

- [Premise Staleness Rules]({{< relref "/docs/development/premise-staleness" >}}) — evidence classes, what each answer does to the baseline, unattended runs and limits.
- [Task Format]({{< relref "/docs/development/task-format" >}}) — the `premise_baseline` and `file_references` fields.
- [Creating Tasks from Code]({{< relref "/docs/workflows/create-tasks-from-code" >}}) — the most common way a task gets a scope and a baseline.
- [Manual Verification]({{< relref "/docs/workflows/manual-verification" >}}) — human-checked verification tasks, which this check skips.
- [`/aitask-pick`]({{< relref "/docs/skills/aitask-pick" >}}) — the workflow the check runs in.
- [Task management commands]({{< relref "/docs/commands/task-management" >}}) — `ait create` and `ait update` flags.
