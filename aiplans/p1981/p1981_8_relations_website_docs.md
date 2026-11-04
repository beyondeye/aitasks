---
Task: t1981_8_relations_website_docs.md
Parent Task: aitasks/t1981_task_relations_and_obsolescence_design.md
Sibling Tasks: aitasks/t1981/t1981_1_relations_store_and_cli.md, aitasks/t1981/t1981_2_relation_candidate_generator.md, aitasks/t1981/t1981_3_relations_worker_and_analysis.md, aitasks/t1981/t1981_4_relations_triggers.md, aitasks/t1981/t1981_5_relations_consumption.md, aitasks/t1981/t1981_6_obsolescence_layer.md, aitasks/t1981/t1981_7_relations_tui.md, aitasks/t1981/t1981_9_port_relations_skill_changes.md, aitasks/t1981/t1981_10_relations_retrospective.md
Archived Sibling Plans: aiplans/archived/p1981/p1981_*_*.md
Base branch: main
Output branch: main
---

# t1981_8 — Relations website documentation

## Context

User-facing docs for what t1981_4 to t1981_7 shipped. Write them from the
landed scripts and skills, using `aidocs/framework/task_relations.md` as the
design anchor only.

## Steps

0. **Reality check.**
   - Run `ait relations --help` and `ait obsolete --help` to get the shipped
     verbs and flags.
   - Read the shipped related-work procedure and the Step 8e text.
   - Read the TUI's actual keybindings.
   - Read `aidocs/framework/documentation_conventions.md`.
1. **Concept page** (`website/content/docs/concepts/`, following the
   concept-page rules in the documentation conventions):
   - relations and the vocabulary;
   - off by default, the cost of enabling it, and how to enable it;
   - the three states (disabled / not analysed / analysed with 0 relations);
   - the hybrid model;
   - obsolescence: never automatic, dismissals.
2. **Command reference** for `ait relations` and `ait obsolete`.
3. **Workflow pages**: the related-work check at pick time and at Step 8, the
   Step 8e flow and its incomplete-analysis choices, `/aitask-note` store-first.
4. **TUI page** under `website/content/docs/tuis/`, and the `tuis/_index.md`
   list.
5. **Task format**: `archived_reason: obsolete`, if t1981_6 did not add it.

## Verification

- `cd website && hugo build --gc --minify`.
- `python3 check_links.py --build` is clean.
- Offer `python3 check_link_relevance.py` for the new links.
- Grep every documented verb and flag in the shipped scripts.

## Step 9

Post-implementation per task-workflow Step 9.
