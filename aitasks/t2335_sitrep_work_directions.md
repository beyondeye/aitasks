---
priority: high
effort: high
depends: []
issue_type: feature
status: Ready
labels: [sitrep, trails, tui, skills]
children_to_implement: [t2335_3, t2335_4, t2335_5, t2335_6]
anchor: 2175
created_at: 2026-11-19 05:12
updated_at: 2026-11-25 19:24
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
5. **Terminology: "direction" everywhere (user-confirmed 2026-11-19).** "Theme" is too vague and is retired as a user-facing word. The TUI, the skill's codes and help (`>d <direction>`, `>w <direction>`), result lines, the website and `aidocs/framework/sitrep.md` say "direction" only. The store renames with the format bump: format 4 writes the context key `direction:` and "situation per direction"; formats 1-3 are still read with `theme:` and upgraded by the first changing write. Internal identifiers (`THEME_RE`, `store.situations`, `RECOVERY_THEME`, CLI `--theme`) are renamed in the child that touches them, with no user-visible alias left behind; each child greps its own surfaces for a leftover "theme".

## Design constraints for every child

- Sitrep stays advisory: nothing here picks, pushes, edits tasks or types into another pane.
- The store has ONE writer (`aitask_sitrep_todo.sh`); every direction write goes through writer verbs with `--expect-rev`.
- Helpers report evidence, the agent judges: the digest, drift reasons, membership and the critical path are deterministic helper output; grouping, ranking and summary prose are the agent's, confirmed by the user.
- The direction's identity is its slug (today's theme slug) (stable across refreshes and re-proposals), never its title or summary text.
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

## Inbox
<!-- Appended by the note framework. Do not edit by hand; use `./ait note`. -->

> **✉ note:t2334** id=2026-11-20T07:08:20Z.0c6ee609e8390416c2bcf010 from=t2334 from_verified=yes at=2026-11-20T07:08:20Z base=514783b73392cffafd76fbdf818e1087726cb05b base_branch=main dirty=yes host=omg16
>
> | Advisory (tree-relative, as of commit 514783b73): t2334 landed the item-type tab strip the "Directions" tab is meant to join. How it is built, in case it changes your child 5's approach:
> | 
> | - Tabs are descriptors: `ListTab(id, label, short, mark, item_type)` in `LIST_TABS` (.aitask-scripts/sitrep_tui/sitrep_tui_model.py). `item_type=None` currently means "All" (every item), and `ListTab.holds()` assumes every tab filters items. A non-item tab therefore needs either a new descriptor field (e.g. a kind/view discriminator) or a separate descriptor type, plus a branch in `SitrepTuiApp._rebuild_list` (sitrep_tui_app.py) to render its own rows instead of the grouped items.
> | - `tab_counts()` counts open items per tab; a Directions tab would need its own count source (or none) in `_render_tabs`.
> | - The strip widget (`ItemTabStrip` / `strip_segments` in sitrep_tui_widgets.py) needs, per tab: label, short label, a one-character `mark` that must stay distinct from A ? T R W (a test pins distinctness), and a count. Narrow layouts are measured so all tabs fit at 30 columns; a sixth tab shrinks the equal-share budget of the capped layout (5 tabs fit from 19 cells; 6 need 6*3+5 = 23), and tests in tests/test_sitrep_tui_app.py (`ItemTypeTabTests`, `TabTests`) assert exactly five tabs/marks in places.
> | - left/right are `priority` bindings gated by `_MAIN_ACTIONS` (needed: the focused OptionList also binds those keys).
