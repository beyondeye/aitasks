---
Task: t1981_6_obsolescence_layer.md
Parent Task: aitasks/t1981_task_relations_and_obsolescence_design.md
Sibling Tasks: aitasks/t1981/t1981_1_relations_store_and_cli.md, aitasks/t1981/t1981_2_relation_candidate_generator.md, aitasks/t1981/t1981_3_relations_worker_and_analysis.md, aitasks/t1981/t1981_4_relations_triggers.md, aitasks/t1981/t1981_5_relations_consumption.md, aitasks/t1981/t1981_7_relations_tui.md, aitasks/t1981/t1981_8_relations_website_docs.md, aitasks/t1981/t1981_9_port_relations_skill_changes.md, aitasks/t1981/t1981_10_relations_retrospective.md
Archived Sibling Plans: aiplans/archived/p1981/p1981_*_*.md
Base branch: main
Output branch: main
---

# t1981_6 — Obsolescence layer

## Context

The second layer of `aidocs/framework/task_relations.md`, covered by D9. It is
never auto-actioned. It uses the store from t1981_1, the worker and headless
operation from t1981_3, and the related-work check from t1981_5.

## Steps

0. **Reality check.**
   - Re-read D9 and the D2 obsolescence record and dismissal.
   - Check whether **t1663_1** (`aitask_premise_stale.sh`, `lib/task_premise.py`)
     has landed: it decides the `premise` row (verdict or `unavailable`).
   - Re-verify `aitask_archive.sh` `main`, `--superseded` and its
     `archived_reason` write.
   - Find the `## Revert Notes` template in `aitask-revert/SKILL.md.j2`.
   - Re-verify `lib/followup_origin.py`.
1. **`lib/obsolescence_evidence.py`** + **`aitask_obsolete.sh evidence
   <id>`**.
   - Rename-aware path history: one `git log --all -M --name-status
     --diff-filter=DR -z` pass, cached in `.aitask-cache/` keyed on HEAD.
   - Suffix and relative resolution through `plan_paths`.
   - Origin state through `followup_origin`, plus a `## Revert Notes` reader
     (a new function; it parses the template's fields).
   - Store-relation rows.
   - The premise row.
   - The age row, labelled as a weak prior.
   - `evidence_digest` over the sorted rows.
2. **The prompt**
   `.aitask-scripts/relations/prompts/obsolescence_assessment.md`. Bands, reasons
   citing evidence ids, and a disposition: `keep|refresh|fold_into|drop`, plus
   `fold_target` for `fold_into`. If there is no row other than `age`, the
   band is `none`, and this is decided in code without calling the agent.
3. **The worker job** for `obsolescence` in `lib/relations_worker.py`: write
   `obsolescence/t<id>.json`.
4. **The landed trigger** in `aitask_archive.sh` `main`, after the archive
   commit, only for completed work: Done, with no `archived_reason`. It does not
   fire for `--superseded`, `--obsolete` or folded archives. Enqueue
   `obsolescence` for the pending tasks in relations(landed) and for the tasks
   whose origin is the landed task. It is silent, and `|| true`.
5. **`aitask_obsolete.sh`** and the `ait obsolete` dispatch: `ls [--min-band]`,
   `show`, `evidence`, `dismiss <id> [--note]` (writes `dismissals/t<id>.json`
   with the current `evidence_digest`), `review` (interactive, one explicit
   choice per item), `sweep [--budget N]`.
6. **`aitask_archive.sh --obsolete`.** It writes `archived_reason: obsolete`.
   Update `website/content/docs/development/task-format.md`, and follow the
   extension-points checklist.
7. **Pick-time display.** The related-work procedure (t1981_5) shows the task's
   own band when it is medium or higher, with its top reasons.
8. **Helper whitelist touchpoints** for `aitask_obsolete.sh`.

## Verification

- `tests/test_obsolescence_evidence.py`: deleted vs renamed vs relative paths;
  a reverted origin; an archived or folded origin; the premise row present and
  unavailable; a stable digest.
- Worker tests: only `age` → `none` with no agent call; a stub agent output is
  validated.
- A dismissal hides the task until the digest changes.
- `--obsolete` writes the reason.
- The landed trigger enqueues the related tasks and never fails an archive.
- `shellcheck`.

## Step 9

Post-implementation per task-workflow Step 9.
