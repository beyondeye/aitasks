---
Task: t1981_2_relation_candidate_generator.md
Parent Task: aitasks/t1981_task_relations_and_obsolescence_design.md
Sibling Tasks: aitasks/t1981/t1981_1_relations_store_and_cli.md, aitasks/t1981/t1981_3_relations_worker_and_analysis.md, aitasks/t1981/t1981_4_relations_triggers.md, aitasks/t1981/t1981_5_relations_consumption.md, aitasks/t1981/t1981_6_obsolescence_layer.md, aitasks/t1981/t1981_7_relations_tui.md, aitasks/t1981/t1981_8_relations_website_docs.md, aitasks/t1981/t1981_9_port_relations_skill_changes.md, aitasks/t1981/t1981_10_relations_retrospective.md
Archived Sibling Plans: aiplans/archived/p1981/p1981_*_*.md
Base branch: main
Output branch: main
---

# t1981_2 — Relation candidate generator and offline replays

## Context

The static candidate generator of `aidocs/framework/task_relations.md` D6, plus
the two offline measurements, D13.1 and D13.2. It depends on t2192 (the shim
over the `aitasks_go#93` engine, with a Python fallback) and on t1981_3
(`ait relations analyze --dry-run`). Its D13.2 report is what the user reads
before enabling analysis in this repository.

## Steps

0. **Reality check.**
   - Read t2192's landed shim. Record its verb names, output protocol,
     `PROVIDER:` line and fallback coverage.
   - Read `aitasks_go#93`'s *Interfaces* mirror in `goengines/README.md`.
   - Map every D6 source tag to a shim verb, or to a framework-side function.
   - If a needed signal is missing from the shim, note it to t2192 / #93
     (`./ait note`) rather than scanning around it.
   - Re-verify `lib/trail_discovery.py`, `lib/parallel_admission*.py`
     (`HUB_THRESHOLD`, OVERLAP rows), `lib/followup_origin.py` and
     `lib/task_yaml.py`.
1. **`lib/relation_candidates.py`**:
   - `candidates(source_id, cap, mode)`:
     - the universe is the pending tasks;
     - collect the evidence rows per source tag;
     - order by the D6 key;
     - give full cards and evidence up to the cap, then list the rest as
       `TRUNCATED:<n>`, as ids grouped by source class. Nothing is hidden;
     - report provider coverage: a failed provider or a missing core verb
       (mentions, cites) is an error exit, which fails the worker's job; a
       missing optional verb (such as `search`) is listed in
       `coverage.missing_sources`.
   - No private path grammar: grammar gaps are raised with t2192 / #93.
   - `mode=fallback_push` (for Step 8e) takes a list of changed paths and
     restricts the universe to Implementing tasks and plan holders whose plan
     cites a changed path. It emits `UNCONFIRMED:` rows.
   - Evidence rows: `{source, detail, section, line?}`. Cards come from the
     shim's `card`.
2. **`aitask_relation_candidates.sh <id> [--json] [--cap N]
   [--fallback-push --changed-file <f>]`**:
   - line protocol + JSON output, with `PROVIDER:` passed through;
   - the helper-whitelist touchpoints.
3. **Point the worker at the real generator.** The worker (t1981_3) calls this
   script. Remove its `CANDIDATES_UNAVAILABLE` stub path, or keep it only for
   when the script fails.
4. **D13.1 replay.**
   - A script that reproduces Appendix A.1 of the seed proposal over this
     generator's output, **task bodies only**.
   - Print recall and candidates per sender, and the aggregate.
   - Run it, and record the result in Final Implementation Notes next to
     `aitasks_go#93`'s numbers.
5. **D13.2 replay.**
   - Select at least 10 senders with at least 4 notes from the note history.
   - Reconstruct each sender's body and plan at its plan-approval commit:
     `./ait git log` on the plan file, then `git show <commit>:<path>` on the
     task-data branch.
   - Run `ait relations analyze --dry-run` with those inputs.
   - Compare the recorded relations with the actual note recipients.
   - Report recall, relation count, the PUSH/PULL split (through
     `notify-candidates` logic, if t1981_5 has landed; otherwise the raw types),
     and tokens, cost and wall time per job.
   - **Record the full report in Final Implementation Notes**, with the
     post-hoc caveat stated.
   - This spends real tokens: confirm the budget with the user before running.

## Verification

- `tests/test_relation_candidates.py`, on a fixture corpus:
  - each source tag;
  - the hub flag;
  - the ordering, the cap and `TRUNCATED`;
  - the fallback-push mode;
  - `PROVIDER` pass-through, with both the engine-absent and the
    engine-present shim (the latter stubbed).
- Both replay reports present in the plan.

## Step 9

Post-implementation per task-workflow Step 9.
