---
Task: t1981_10_relations_retrospective.md
Parent Task: aitasks/t1981_task_relations_and_obsolescence_design.md
Sibling Tasks: aitasks/t1981/t1981_1_relations_store_and_cli.md, aitasks/t1981/t1981_2_relation_candidate_generator.md, aitasks/t1981/t1981_3_relations_worker_and_analysis.md, aitasks/t1981/t1981_4_relations_triggers.md, aitasks/t1981/t1981_5_relations_consumption.md, aitasks/t1981/t1981_6_obsolescence_layer.md, aitasks/t1981/t1981_7_relations_tui.md, aitasks/t1981/t1981_8_relations_website_docs.md, aitasks/t1981/t1981_9_port_relations_skill_changes.md
Archived Sibling Plans: aiplans/archived/p1981/p1981_*_*.md
Base branch: main
Output branch: main
---

# t1981_10 — Relations retrospective

## Context

D13.3 of `aidocs/framework/task_relations.md`: the live evaluation that decides
the choices the design deferred to data. An audit-only outcome is valid.
Follow-up tasks are filed only where the data says "change".

## Steps

0. **Precondition.** Analysis must have been enabled here for at least 4 weeks,
   or at least 100 records must exist (`ait relations status` / `usage`). If
   neither holds, report the counts and stop: Postpone the task with a note.
1. **Collect.**
   - `ait relations usage --days 30+`.
   - The store records.
   - The `pull.jsonl`, `notify.jsonl` and `usage.jsonl` ledgers from every host
     that ran analysis. Ask the user to run `ait relations ledgers --export` on
     each host, then merge the host-tagged outputs.
   - Archive completion times.
   - The D13.1 / D13.2 reports in t1981_2's archived plan.
2. **Answer each question in the task body** with its numbers:
   - the D5 default;
   - stale-relation handling: usefulness, misleading notifications, triggers,
     the display rule;
   - push precision;
   - the incomplete-analysis states and the options chosen;
   - the late-relation gap and the retained-review decision (with the shared
     resolution identity, if a review is built);
   - reverse-lookup cost;
   - the roadmap slot;
   - non-Claude headless support;
   - adoption of `orphan_ref_store.py`.
3. **Write the findings** into this plan's Final Implementation Notes, one
   section per question.
4. **File follow-ups** only for questions the data answers "change", each
   citing its numbers.

## Verification

Every question has a recorded answer backed by numbers, or an explicit "not
enough data", with the counts.

## Step 9

Post-implementation per task-workflow Step 9. This is the last child: archiving
it lets the orphaned-parent path archive t1981.
