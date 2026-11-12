---
title: "Implementation Trails"
linkTitle: "Implementation Trails"
weight: 46
description: "Record which tasks should land next, in what waves, and why — as a durable, refreshable artifact"
depth: [advanced]
---

An implementation trail is a stored, versioned recommendation of which tasks should land next, in what waves, and why. [Implementation trails]({{< relref "/docs/concepts/implementation-trails" >}}) explains why you would keep one.

## What a Trail Records

A trail is organized into **waves**: ordered groups that land as a unit before the next wave starts. Each wave holds ordered **entries**, each referring to a task, and every entry carries its own rationale, a confidence (`high`, `medium` or `low`) and, in a deep trail, links to the evidence behind it.

Each entry is classified by why it is in that position, as a hard prerequisite, a preferred predecessor, core work, coordination only, or optional; the glyph each one shows on a card, and what it means, are in the [board reference]({{< relref "/docs/tuis/board/reference" >}}#by-trail). Only a hard prerequisite is a reason to wait: a coordination-only entry only has to land at a different time.

A deep trail also records two things that are not members:

- **Observations**: evidence-backed facts that shape the ordering without being tasks, such as a failing baseline suite, an in-flight conflict, a task whose premise has gone stale, or a shared file two efforts both edit.
- **Exclusions**: work named as not blocking, so a later reader does not argue it again.

Each observation cites its evidence. Each of a deep trail's relations between entries is marked either as a fact read from the repository, such as a recorded `depends` edge, or as an advisory recommendation the trail is making. A trail never contains time estimates, progress percentages or delivery commitments.

## Creating a Trail

1. Start the creation workflow from one of three places:
   - In the board, focus a task in a kanban view or in By-Topic and press `T`. In By-Topic it starts from the focused lane's topic root instead of the card. `T` is hidden in the In-Flight and By-Trail views; in By-Trail, `R` re-authors the trail you are looking at.
   - In `ait trails`, focus a live member card and press `T`.
   - In your coding agent, run the skill:

     ```
     /aitask-trail                      # asks what the trail should cover
     /aitask-trail 312                  # a single task, or its topic
     /aitask-trail --topics 312,408     # spanning several topics
     ```
2. Choose the depth. Without a flag the trail is **lite**: waves, entries and the narrative. Add `--deep` (`/aitask-trail 312 --deep`) to also record observations, exclusions, relations between entries and per-entry evidence links. A deep trail takes noticeably longer to analyse, so it suits a trail you plan to keep and refresh. The board's `T` and `R` launch the skill without `--deep`, so they produce a lite trail; run the skill yourself for a deep one.
3. Review the proposal. The agent reads task and plan state without changing anything and shows you the proposed waves with their reasoning. If it finds a blocker outside the scope you asked for, such as a broken test baseline unrelated to your topic, a deep trail proposes widening the scope and lets you decide; a lite trail names that work in its overview instead. When the scope has no natural owner task, it asks you to choose one; the owner rules are under [Storage]({{< relref "/docs/skills/aitask-trail" >}}#storage).
4. Confirm. The trail is written once, after your confirmation; nothing is stored before it.

The run ends by printing the trail it wrote: its depth and overview, each wave with its entries in order, the recorded relations, and the keys that open the By-Trail view. In `ait trails`, press `s` and select the new trail; it opens in a new tab. The [run summary]({{< relref "/docs/skills/aitask-trail" >}}#the-run-summary) lists everything the printout contains.

## Reading a Trail on the Board

1. Press `z` for the By-Trail view, then `s` to choose the trail. The view shows one trail at a time. To keep several trails open, one tab each, run [`ait trails`]({{< relref "/docs/tuis/trails" >}}), or press `j` then `i` from any TUI; it opens straight into the trail selector and uses the same keys. Moving tasks into columns (`m`, `M`) and sync (`S`) are only in the board, and the two TUIs keep separate trail selections.
2. Read the waves. Each wave is a column headed `W1 · …`, with its entries in order. A card shows the classification glyph, the confidence and the task's live status; a member whose task is done is marked `✔` and struck through. Members that are not live local tasks (archived, cross-repo or deleted) appear as read-only ghost cards. For members blocked by work in another project, and for `L`, which jumps to linked trails in other projects, see [Cross-repo dependencies in implementation trails]({{< relref "/docs/workflows/cross_project_dependencies" >}}#cross-repo-dependencies-in-implementation-trails).
3. Read the summary pane below the columns: the trail's own answer to "what should land next, and why". Press `v` to open it in a scrollable dialog when it is longer than the pane.
4. Press `Enter` on a card for that member's reasoning: its rationale, its wave, the drift affecting it and, in a deep trail, the evidence behind them. Material about other cards is withheld and shown as a count; press `a` to reveal the whole document and `a` again to go back.

Every key of the view is in the [board reference]({{< relref "/docs/tuis/board/reference" >}}#by-trail).

## Keeping a Trail Current

A trail whose evidence has moved shows `⚠ stale` with the number of drift reasons it found. Drift is, for example, a member being completed, archived, folded or deleted, a status or dependency change, a gate outcome, a rewritten plan, or a new related task.

1. When you open an older trail, press `d` first. It re-checks the stored trail against live task state and updates the badge, and it never writes the trail.
2. If the change was made on another machine, sync first. In the board, `S` runs a full task-data sync, which can pull, push and merge, then redraws. In `ait trails`, run `ait sync` in a shell, then press `r` to re-read the task files, `d` to fetch the trail again and re-check its freshness, and `s` to re-scan the project for trails.
3. If the drift means the reasoning is out of date, press `R`. An agent re-authors the trail and writes a new version after you confirm; every earlier version stays retrievable. `R` re-authors at the lite depth, so run `/aitask-trail --refresh <handle> --deep` to keep a deep trail deep.

Only `R` writes a new version. Moving cards between board columns never makes a trail stale. What each refresh key reads and costs is in the [board reference]({{< relref "/docs/tuis/board/reference" >}}#by-trail) and in [What each refresh reads]({{< relref "/docs/tuis/trails/reference" >}}#what-each-refresh-reads).

## Feeding a Work Report

A trail reaches a [work report]({{< relref "/docs/workflows/work-report" >}}) only through the board columns you move its tasks into.

1. In By-Trail, focus a card in the wave and press `M` to move the whole wave's tasks into a column, or `m` to move only the focused card's task. `M` first lists the tasks for review, keeps wave order, and names the members it skips; see [Moving a wave into a column]({{< relref "/docs/tuis/board/reference" >}}#moving-a-wave-into-a-column).
2. Choose the destination column.
3. Switch to a kanban view (for example `a` for All), focus that column and press `w` to draft the work report as usual.

The report contains exactly the tasks in the columns you selected, in board order. A trail never adds tasks to a report or reorders one. You can draft the report again from the column at any time; the trail keeps the reasoning and its history.

## Where a Trail Is Stored

A trail is one structured document, stored as a [versioned artifact]({{< relref "/docs/concepts/artifacts" >}}) whose handle is an entry in one owner task's `artifacts:` frontmatter. Membership is recorded inside the document, so a task can appear in any number of trails without its own file changing. Who owns a trail, how trails are found (archived owners included), what folding the owner does, and how to list or delete versions are in [Storage]({{< relref "/docs/skills/aitask-trail" >}}#storage) on the `/aitask-trail` page.

## What a Trail Never Does

- It never changes a task's `depends`, `priority`, board position or topic, and it never changes what a work report contains. Turning trail ordering into real dependencies is a decision you make by hand.
- Gate checks, dependency checks and archival never read a trail, so a trail can never block or unblock a task.

The full list is in the skill's [Invariants]({{< relref "/docs/skills/aitask-trail" >}}#invariants). A task belongs to exactly one topic, and one trail may span several topics; see [Topic anchoring]({{< relref "/docs/concepts/topic-anchoring" >}}).

---

**Next:** [Work Report]({{< relref "/docs/workflows/work-report" >}}) — turn a wave you have moved into a column into a manager-facing summary.
