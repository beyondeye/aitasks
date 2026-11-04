---
Task: t1981_7_relations_tui.md
Parent Task: aitasks/t1981_task_relations_and_obsolescence_design.md
Sibling Tasks: aitasks/t1981/t1981_1_relations_store_and_cli.md, aitasks/t1981/t1981_2_relation_candidate_generator.md, aitasks/t1981/t1981_3_relations_worker_and_analysis.md, aitasks/t1981/t1981_4_relations_triggers.md, aitasks/t1981/t1981_5_relations_consumption.md, aitasks/t1981/t1981_6_obsolescence_layer.md, aitasks/t1981/t1981_8_relations_website_docs.md, aitasks/t1981/t1981_9_port_relations_skill_changes.md, aitasks/t1981/t1981_10_relations_retrospective.md
Archived Sibling Plans: aiplans/archived/p1981/p1981_*_*.md
Base branch: main
Output branch: main
---

# t1981_7 — Relations TUI

## Context

The human view (D10 of `aidocs/framework/task_relations.md`): a read-only
Textual `ait relations` TUI with a Relations tab and an Obsolete tab,
registered in the switcher, plus a board detail field. It depends on t1981_6,
so both record kinds exist.

## Steps

0. **Reality check.**
   - Read `aidocs/framework/tui_conventions.md`: the board package layout,
     keybinding rules, the switcher, shared screens.
   - Read `aidocs/framework/testing_conventions.md`: `App.run_test` and `@work`.
   - Look at `ait trails` (`board/trails_app.py`) as the closest read-only
     analogue.
   - Re-verify `KNOWN_TUIS` in `lib/tui_switcher.py`.
1. **Data layer.** A thin adapter over `aitask_relations.sh show --json`,
   `aitask_obsolete.sh ls --json` and `show --json`. No direct store access, so
   the TUI uses the same state lines as agents.
2. **The Relations tab.**
   - A task picker.
   - A table of the task's relations: direction, type, other task, freshness,
     confirmation, stage.
   - A detail pane with the description, basis and evidence.
   - Neighbourhood: one hop.
   - A banner for the disabled / empty / stale store states.
3. **The Obsolete tab.**
   - The list sorted by band, with reasons and evidence in a detail pane.
   - Actions that call the CLIs: open in board, `ait note`, fold flow, `ait
     obsolete dismiss`, `aitask_archive.sh --obsolete`. Destructive actions ask
     for confirmation.
4. **Launcher and switcher.** The launcher `.sh`, the `ait relations tui` (or
   `ait relations-tui`) entry, and a `KNOWN_TUIS` registration.
5. **Board detail field.** "Relations: n (k stale)", with a key that opens the
   TUI on that task. Follow the keybinding-override rules: test dispatch, not
   only the render.

## Verification

- `App.run_test` tests over fixture JSON:
  - both tabs render;
  - the state banners;
  - the actions dispatch the right command (stubbed);
  - keybinding dispatch;
  - the switcher entry;
  - the board field and its key.
- No `@work` worker left in flight at block exit.

## Step 9

Post-implementation per task-workflow Step 9. The website page is t1981_8.
