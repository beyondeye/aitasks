---
priority: medium
effort: high
depends: []
issue_type: feature
status: Ready
labels: [brainstorming, task_relations, task-workflow, backlog]
gates: [risk_evaluated]
created_at: 2026-10-14 12:17
updated_at: 2026-10-14 12:17
---

Design a **task-relations layer** for the aitasks framework. Background agents
maintain a store of confirmed task-to-task relations, kept separate from the task
files, and the store becomes the source of the end-of-implementation notify list.
On the same infrastructure, add a **backlog-obsolescence layer** that gives pending
tasks an obsolete score with reasons. Both are viewable in a TUI later. The
relations data is meant first of all for code agents.

**This is a brainstorming task. Its output is a design document.** The seed
proposal (three rounds of exploration on 2026-10-14) is attached to this task as
`task_relations_proposal.md`. It holds the findings, the measurements with
reproducible scripts (Appendix A), the decisions already taken, and the open
design directions D1–D13. Import it as the brainstorm root node with
`ait brainstorm init <this task> --proposal-file <the attachment>`. The design is
deliberately NOT final. Work from the premises below and analyse the design
directions until they are settled.

## Why

- Today, `task-workflow` Step 8e (and the matching offers in `aitask-qa` and
  `aitask-review`) chooses note recipients by agent judgement alone. With no
  target, `/aitask-note` runs Related Task Discovery: every pending task's
  title, labels and first ~5 body lines. No file surfaces, `depends`, trails or
  past note edges are used.
- Doing it well costs the implementing session real context. t1794 needed a
  whole child task (t1794_9) to grep 103 candidates and send 63 notes.
- Doing it broadly is harmful. There are 373 note commits and 52 read-receipt
  commits on the shared task-data branch, each one a push race on the hottest
  files. Over-notification is a defect.
- Nothing identifies backlog tasks that are obsolete: tasks whose goal was met
  elsewhere, whose direction was superseded, whose origin was reverted, or whose
  target code is gone. t1663 / t1655 (premise staleness, not built) explicitly
  exclude "is this still worth doing?".

## Decisions taken so far

1. Precision over recall. Notify only tasks with real connections; in doubt,
   exclude.
2. A task-relations store, conceptually an extension of task metadata, stored
   separately from the task files.
3. Written by background agents when a task is created and when its plan is
   finalized (approved) before implementation.
4. The agents start from static analysis (metadata, task cross-references,
   labels, file citations) to build candidates, then analyse them and record
   only confirmed relations, each with a description of the relation.
5. The end of implementation reads the store for the notify list.
6. Obsolescence is a second layer on the same infrastructure, with different
   search logic and an obsolete score with reasons. Never auto-actioned.
7. A TUI for relations and obsolete tasks comes later. Agents are the first
   consumers.
8. Rejected as the primary mechanism: a purely static, in-session dependency
   analyzer at the end of each task. It stays as the candidate generator.

## Key measurements (details and scripts in the attachment)

- Replay of 13 real senders (143 notes):
  - Task-id cross-references in task bodies find 86% of actual recipients at
    ~23 candidates per task.
  - File overlap finds 95%, but at ~290 candidates per task.
  - Labels find 24%. Metadata edges alone find 26%.
- Static indexing is cheap: 0.15 s for 594 tasks + 130 plans.
- Analysis triggers run at about 12 per day (234 tasks and 129 plans in 30 days).
- Of 577 pending tasks, 184 cite a path missing at HEAD. Most are renames,
  relative paths or planned-new files. Only 3 cite a truly deleted file.
  Obsolescence needs judgement over static evidence.

## Open design directions (see the attachment)

- D1: store location (separate `aitask-relations` branch written like
  `aitask-locks`, vs a one-file-per-record directory on the data branch).
- D2: record schema, vocabulary and provenance digests.
- D3: single-writer records with forward ∪ reverse lookup.
- D4: triggers (four `aitask_create.sh` commit sites, plan approval at Step 7
  and in `plan-approved-stop.md`, landed/archived, fold, sweep).
- D5: execution (headless `relations` op, spool, single worker, budget,
  opt-out).
- D6: static candidate generation.
- D7: the agent's inclusion test.
- D8: push (notes) vs pull (pick-time surfacing from the store) vs hybrid.
- D9: obsolete score evidence and dispositions.
- D10: surfaces and TUI.
- D11: freshness and lifecycle.
- D12: cross-repo.
- D13: evaluation.

## Related tasks

- t1663 (+ children) and t1655: premise staleness, the "needs refresh" axis.
  Coordinate; do not duplicate.
- t1634: fold-candidate clustering, a likely producer or consumer of
  duplicate-type relations.
- t1569 / t1718: background-work roadmap.
- t1657 family and `aidocs/framework/task_note_mailbox.md`: the note mailbox.

## Expected outcome

A finalized design document at `aidocs/framework/task_relations.md` covering
D1–D13, and a decomposition into child tasks. A plausible split:
- relations store and CLI
- static candidate generator
- background worker, headless op and spool
- creation and plan-approval triggers
- Step 8e / pick-time consumption
- obsolescence layer
- TUI
- ports of the skill changes to the other code agents
