---
title: "Implementation Trails"
linkTitle: "Implementation Trails"
weight: 46
description: "Record which tasks should land next, in what waves, and why — as a durable, refreshable artifact"
depth: [advanced]
---

When several tasks are in play at once, the most valuable thing you work out is rarely captured anywhere. The dependency graph records which tasks *cannot* start yet. The board records which tasks you *want* first. Neither records the thing you actually reasoned your way to: **which tasks should land next, in what waves, and why** — that this one is a true blocker, that one is a cheap fix worth doing first, that a third only overlaps on a shared file and needs sequencing rather than waiting, and that a red test suite outside the topic entirely is the real thing standing in the way.

That analysis is expensive to produce and, until now, it lived in terminal scrollback until the window closed.

**An implementation trail makes that answer durable: a versioned artifact holding the recommended landing order together with the reasoning and the evidence behind it, which you can re-open weeks later, refresh when reality moves, and read on the board as wave columns.**

## What a Trail Records

A trail is organized into **waves** — ordered groups that land as a unit before the next wave starts. Each wave holds ordered **entries**, each referring to a task, and every entry carries its own rationale, a confidence level, and links to the evidence behind it.

Each entry is classified by *why it is in that position*:

| Glyph | Classification | Meaning |
|---|---|---|
| `◆` | Hard prerequisite | A true blocker — the later work cannot proceed until this lands |
| `▲` | Preferred predecessor | Not strictly blocking, but markedly cheaper or safer to do first |
| `●` | Core | The substance of the trail — the work it exists to sequence |
| `⇄` | Coordination only | No dependency, but it touches a shared surface, so it should not land concurrently |
| `○` | Optional | Related and worth doing, but the trail does not depend on it |

<!--
  Drift note for maintainers — this page states two things with two different
  canonical sources. Update it when either moves:
    * the five classification names -> the `entry.classification` enum in
      .aitask-scripts/lib/implementation_trail.schema.json
    * the glyph mapping (◆ ▲ ● ⇄ ○) -> TRAIL_CLASSIFICATION_GLYPHS in
      .aitask-scripts/board/aitask_board.py
  The schema does NOT define the glyphs; checking it alone will not catch a
  glyph change.
-->

Distinguishing a hard prerequisite from a coordination-only overlap is most of the value. Both look like "do that one first" on a board, but only one of them is a reason to wait.

Alongside the waves, a trail records two things that are *not* members:

- **Observations** — evidence-backed facts that shape the ordering without being tasks themselves: a failing baseline suite, an in-flight conflict, a task whose premise has gone stale, a shared file two efforts both edit.
- **Exclusions** — work deliberately named as *not* blocking, so a later reader does not re-litigate it.

Everything the agent asserts is separated from what it observed: observations cite evidence, and recommendations are recorded as recommendations. A trail never invents time estimates, progress percentages, or delivery commitments.

## Creating a Trail

**From the board** — focus a task in one of the kanban views or By-Topic, and press **`T`**. In By-Topic this resolves to the focused lane's topic root, so you get a trail for the whole topic rather than the one card. `T` is not available in the In-Flight or By-Trail views; from By-Trail, use **`R`** to re-author the trail you are already looking at.

**From your agent** — invoke the skill directly:

```
/aitask-trail                      # asks what the trail should cover
/aitask-trail 312                  # a single task, or its topic
/aitask-trail --topics 312,408     # spanning several topics
```

The flow is the same either way: the agent gathers task and plan state read-only, analyses it, shows you the proposed waves with their reasoning, and writes **once** after you confirm. Nothing is stored until you approve it, and analysis never modifies a task.

If the analysis turns up a blocker outside the scope you asked for — the classic case being a broken test baseline that has nothing to do with your topic — it proposes widening the scope and lets you decide. It does not quietly expand on its own.

### Lite and Deep

Trails come at two depths:

```
/aitask-trail 312            # lite (the default)
/aitask-trail 312 --deep     # full analysis
```

**Lite** produces the waves, entries, and narrative — the part you act on. **Deep** adds observations, exclusions, cross-entry relations, and per-entry evidence links. Deep costs meaningfully more analysis time, so it suits a trail you expect to keep and refresh rather than a quick sequencing question.

Omitting the flag always means lite, including when the board re-authors a trail for you. A trail records the depth it was written at, and a trail written before depth was recorded shows no label at all — an unlabelled trail means "depth not recorded", never "deep".

## Reading a Trail on the Board

Press **`z`** for the By-Trail view, then **`s`** to choose which trail to show. Exactly one trail is active at a time.

Each wave becomes a column headed `W1 · …`, with entries in order. Cards carry the classification glyph, the confidence, and the task's live status — a member that has since been completed shows struck through, so a partially-landed wave is obvious at a glance. Members that are not live local tasks — archived, cross-repo, or since deleted — appear as read-only ghost cards.

Below the columns sits the **summary pane**: the trail's prose answer to "what should land next, and why". Press **`v`** to open it full-screen when it outgrows the pane.

Press **`Enter`** on a card for that member's own reasoning. The detail screen leads with the focused entry — its rationale, its wave, the drift affecting it, and the evidence behind both — and withholds the trail-wide material that belongs to *other* cards, summarizing it as a count. Press **`a`** to reveal the whole document and **`a`** again to go back.

## Keeping a Trail Current

A trail is a snapshot of reasoning, so the useful question is whether reality has moved since it was written. The board tells you: a stale trail carries a `⚠ stale` badge naming how many reasons it found. Drift is things like a member being completed, archived, folded or deleted; a status or dependency change; a gate outcome; a plan being rewritten; or a new related task appearing.

Four keys refresh different things, and they are worth knowing in cost order — reach for the cheapest that answers your question:

| Key | Cost | What it does |
|---|---|---|
| `r` | instant | Re-reads task files from disk and redraws — no subprocess, no agent |
| `d` | seconds | Re-checks the stored trail against live task state and updates the freshness badge |
| `S` | slower | Syncs task data with the remote (pull / push / merge), then recomputes |
| `R` | an agent run | Hands the trail to an agent to be re-authored, producing a new version |

Only **`R`** writes a new trail version — `r` and `d` are read-only projections of what is already stored. **`S`** does not author a trail either, but it is not read-only: it runs a full task-data sync, which can pull, push and merge, exactly as syncing from any other view does.

Refreshing is targeted rather than wholesale: it re-analyses what the named drift reasons actually implicate and produces a new version, and every earlier version remains retrievable.

> **Moving cards around does not stale a trail.** Board column and position are deliberately excluded from the freshness computation, so reorganizing your board — including the wave moves below — never makes a trail look out of date.

## Feeding a Work Report

Trails and [work reports](../work-report/) connect through the board column, and nothing else.

With a wave in view, press **`M`** to move that whole wave's tasks into a board column, in wave order. Press **`m`** to move just the focused card. Then run the work report on that column with **`w`** as you normally would.

This is deliberately a manual bridge. A report contains exactly the tasks you selected, in board order — a trail never adds tasks to a report or reorders one behind your back. Its influence reaches a report only through a move you performed and can see on the board first.

A few details worth knowing about `M`:

- It **always** shows you the task list for review before asking for a destination.
- It preserves wave order exactly, so a wave moved into an empty column lands in the order the trail recommends.
- It tells you what it is skipping and names the items — read-only ghost members, and child tasks that move with their parent — rather than reporting a bare count.

Ghost members cannot be moved at all: there is no local task file behind them, and the board says so instead of failing quietly.

## What a Trail Never Does

A trail is **advisory by construction**. It records a recommendation; it does not enforce one.

- It never rewrites `depends`, `priority`, board position, or a task's topic. Converting trail ordering into real dependencies stays a decision you make by hand.
- It never changes what a work report contains.
- It never fabricates estimates, progress, or commitments.
- Analysis is read-only and every stored change is a single write you confirmed.

Topic membership and trail membership are separate on purpose: a task belongs to exactly one topic, but it may appear in several trails, and one trail may span several topics. See [Topic anchoring]({{< relref "/docs/concepts/topic-anchoring" >}}).

## Tips

- **Reach for a trail when the ordering question is expensive, not routine.** A handful of tasks with obvious dependencies does not need one; a dozen tasks across three topics with a shaky baseline underneath is exactly the case it pays for.
- **Start lite.** Add `--deep` when a trail has earned its keep and you want the evidence trail with it.
- **Refresh before you trust an old trail.** Press `d` when you re-open one — it is cheap, and a stale badge is more useful than a confident-looking wave that has already half landed.
- **Let the summary do the talking.** When someone asks what is next, the summary pane is already the answer, written when the reasoning was fresh.
- **Trails are durable; reports are drafts.** Keep the trail, regenerate the report.

---

**Next:** [Work Report](../work-report/) — turn a wave you have moved into a column into a manager-facing summary.
