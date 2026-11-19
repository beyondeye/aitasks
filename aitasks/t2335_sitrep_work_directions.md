---
priority: high
effort: high
depends: []
issue_type: feature
status: Ready
labels: [sitrep, trails, tui, skills]
children_to_implement: [t2335_1]
anchor: 2175
created_at: 2026-11-19 05:12
updated_at: 2026-11-19 05:12
---

## Problem

The sitrep list is a list of items without a direction. It tells what is pending, not which lines of work are active, how they rank against each other, what the next step of each one is, or what blocks it. Implementation trails already sequence tasks (waves, typed relations, a `current / stale / unknown` verdict), but nothing connects them to "current work": the items in the sitrep store.

## Goal

**Work directions**: a persisted, ranked set of active lines of work in the sitrep store, created and maintained by the sitrep agent, checked for staleness deterministically, shown as summaries in the sitrep TUI, queryable in the sitrep agent window, and linked to implementation trails with the direction's tasks and their critical path highlighted.

## Decisions (user-confirmed 2026-11-19)

1. **Data model: promote themes.** A direction IS the existing `theme` (the slug every context entry may name, with its agent-written situation text), extended to a first-class record: title, rank, linked trail handle(s), summary, next step, input digest and freshness. No second grouping concept. Store format bump to 4.
2. **Trails: overlay, create only if uncovered.** A direction reuses existing trails through a highlight + critical-path overlay computed from the direction's tasks. Only when no trail covers a direction's tasks does the agent offer to create one with `/aitask-trail` (ad_hoc / multi_topic scope). Never one generated trail per direction by default.
3. **Ranking: agent proposes, user confirms.** The order among directions is proposed by the agent with reasons, confirmed or reordered by the user, and persists until changed. Not a recomputed score.
4. **TUI: one tab strip.** A "Directions" tab is appended to the item-type tab strip (separate task): ranked rows with freshness, next task, item count and a one-line summary, plus an "N items in no direction" line.

## Design constraints for every child

- Sitrep stays advisory: nothing here picks, pushes, edits tasks or types into another pane.
- The store has ONE writer (`aitask_sitrep_todo.sh`); every direction write goes through writer verbs with `--expect-rev`.
- Helpers report evidence, the agent judges: the digest, drift reasons, membership and the critical path are deterministic helper output; grouping, ranking and summary prose are the agent's, confirmed by the user.
- The direction's identity is its theme slug (stable across refreshes and re-proposals), never its title or summary text.
- The digest covers every input the summary was written from; staleness is `current / stale / unknown`, and an input that cannot be read is `unknown`, never `current`.
- The virtual `crashed-agents` theme (recovery items name no theme; the mapping is read-side) must stay coherent: decide in child 1 whether it becomes a derived direction or stays outside the ranked set, and apply that everywhere.

## Children

1. Store: direction records, writer verbs, format 4.
2. Refresh: deterministic direction freshness.
3. Trails: highlight set and critical-path overlay in `ait trails`.
4. Skill: the `>d` directions code, summaries, ranking, questions, pick advice.
5. TUI: the Directions tab.
6. Manual verification of the whole flow.

The item-type tab strip is a separate task that child 5 depends on.

## Reference

`aidocs/framework/sitrep.md` (whole feature), `aidocs/framework/tui_conventions.md`, `.aitask-scripts/lib/implementation_trail.schema.json`, `aidocs/framework/planning_conventions.md`.
