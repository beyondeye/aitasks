---
title: "Premise Staleness Rules"
linkTitle: "Premise Staleness"
weight: 15
description: "Which tasks the premise staleness check evaluates, the evidence it reports, what each answer does to the task and its premise baseline, how unattended runs behave, and the check's limits"
depth: [advanced]
---

The premise staleness check compares a `Ready` task's scope at its `premise_baseline` commit with the current commit, and asks you what to do when it finds evidence of drift. [Premise Staleness Check]({{< relref "/docs/workflows/premise-staleness" >}}) covers answering the prompt and opting a task in or out; the stored format of the field is in [Task Format]({{< relref "/docs/development/task-format" >}}#frontmatter-fields).

## Which tasks it evaluates

The check runs at the start of the shared task workflow, after a task is selected and before it is claimed. Every route into that workflow reaches it: [`/aitask-pick`]({{< relref "/docs/skills/aitask-pick" >}}), launching an agent on a task from the board, and [`/aitask-explore`]({{< relref "/docs/skills/aitask-explore" >}}) handing off to implementation.

It evaluates a task only when all of these hold:

- the task's status is `Ready`;
- the task is not a `manual_verification` task;
- the task carries a stored `premise_baseline`;
- the task has a scope the check can derive. A non-empty `file_references` list is the scope; a line range on an entry (`path:N-M`) is ignored and the whole file is checked. Without `file_references`, a task with a `verifies` list takes as its scope the files that the verified tasks' own commits touched.

Every other task is skipped silently. Besides the cases above, a skip covers a `premise_baseline` that is not a full commit id (for example a hand-edited `HEAD`), a baseline commit that is no longer an ancestor of the current commit (for example after a history rewrite), frontmatter that is not valid YAML, a scope that could not be resolved, and a scope whose every file was deleted at or before the baseline. The check is also silent when every file in the scope was checked and none of them changed.

A carry-over task, which archival creates for a `manual_verification` task's deferred checklist items, inherits its source task's `premise_baseline`. Carry-over tasks are always `manual_verification` tasks, so this check never reads the inherited baseline.

## Evidence

The check compares the baseline commit with the current `HEAD`, path by path over the task's scope. It reads committed history only: uncommitted edits in the working tree are invisible to it.

| Evidence | Meaning |
|---|---|
| Changed | Commits touched the file since the baseline. The prompt names how many, and which tasks made them. |
| Deleted | The file was removed since the baseline. The prompt names the task that removed it and the commit's subject. |
| Added since the baseline | The file did not exist at the baseline and exists now, or was touched in between. |
| Never existed | The file exists neither at the baseline nor now, and no commit ever touched it: either a file the task intends to create, or a typo. The check cannot tell the two apart. |
| Invalid reference | A `file_references` entry that is not a usable path, such as an unquoted word YAML reads as a number or a boolean. |
| Could not be checked | The history query for a path failed, or the origin of a `verifies` scope could not be read. |

The first three are changes. The last three are unresolved scope or history, and they trigger the prompt too, even though no committed change was found: an entry the check cannot confirm is never treated as an all-clear. A file deleted at or before the baseline is not evidence and is not reported.

The prompt shows the first 10 evidence rows inside the question and summarises the rest; every row is kept for a replan.

## Answers and the baseline

Under an interactive execution profile on the shared workflow, the question is always asked when there is evidence. No profile key skips it, because the answer is what allows the baseline to move.

| Answer | What happens | The baseline |
|---|---|---|
| Proceed — premise still valid | The task is claimed and the workflow continues as normal. | Advances to the commit that was checked. |
| Review & replan with this evidence | The task is claimed and planning starts with the evidence as input. If the task already has a plan, that plan is re-verified rather than reused as-is. The plan records a review of every evidence row. | Advances once the renewed plan is approved, including when you approve it and stop there, and only when the plan records a review of every evidence row. Unchanged if the plan is never approved. |
| Postpone task | The task is claimed, set to `Postponed`, and the session ends. To bring it back, run `ait update --batch <id> --status Ready`. | Unchanged. |
| Pick a different task | Nothing is written; you go back to task selection. | Unchanged. |

## Rules that shape the answers

- **The question is asked before the task is claimed, and nothing is written until after.** Another session can claim a `Ready` task while the question is open, so the claim re-checks, under the task lock, that the task is still `Ready`. If it changed meanwhile, nothing is claimed and you go back to task selection.
- **The baseline moves only to the commit you were shown.** Commits that land between the question and the write are not marked as reviewed; they surface at the next pick.
- **An answer about changed inputs is void.** If the task's scope or stored baseline changed between the question and the write, the baseline does not move. When a fresh check still finds evidence, the question is asked again.
- **References to files that never existed get their own question.** After "Proceed", the workflow asks whether to keep or remove them from `file_references`. Keeping them is the default, since they may be files the task will create. If the list also holds an invalid entry, no reference can be removed in that write; the baseline still advances.
- **Unverifiable evidence blocks the advance.** If any path could not be checked, "Proceed" claims the task but leaves the baseline where it is, and the check runs again on the next pick, because advancing would mark commits nobody saw as reviewed.
- **Invalid references cannot be cleared from the prompt.** They are reported until you fix the `file_references` entry by hand.

## Unattended runs

- **A non-interactive execution profile on the shared workflow** (one with `headless: true`, such as `remote`) runs the check and, when there is evidence, displays it and continues. It never prompts, never advances the baseline and never postpones the task, since each of those needs a person's confirmation, so the same evidence is shown again at the next attended pick.
- **The autonomous [`/aitask-pickrem`]({{< relref "/docs/skills/aitask-pickrem" >}}) and [`/aitask-pickweb`]({{< relref "/docs/skills/aitask-pickweb" >}}) skills** run their own workflow and do not run the check at all.

## Limits

- **Tasks without a stored baseline are skipped.** There is no backfill: existing tasks join only when a baseline is set, at creation or by hand.
- **There is no time-based verdict.** Age alone never triggers the check; only evidence about the scope does.
- **It measures commits to the scope files.** A behaviour-preserving refactor of a scope file reads as a change, and a change elsewhere that invalidates the premise reads as clean.
- **A kept reference to a file that never existed keeps being reported** until the file is created or the reference removed.
- **A session that cannot identify itself cannot advance the baseline.** The advance requires proof that this session holds the task's lock: the lock must name the claiming email on this host and this agent session. A session is identified by the agent's tmux pane or, outside tmux, by `AIT_AGENT_PID` (the same session anchor the [merge mutex]({{< relref "/docs/development/merge-mutex" >}}#the-session-anchor) uses). A session running outside the agent's tmux pane without `AIT_AGENT_PID`, or a lock that records no session anchor, cannot give that proof, so the baseline stays put and the question comes back on the next pick.
- **A draft is stamped when it is finalized.** A change that lands while a draft waits in `aitasks/new/` is not reported.
