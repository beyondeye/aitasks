---
priority: medium
effort: medium
depends: [t1981_3, 2192]
issue_type: feature
status: Ready
labels: [task_relations, backlog]
gates: [risk_evaluated]
anchor: 1981
created_at: 2026-11-04 15:39
updated_at: 2026-11-04 15:39
---

## Context

Child of t1981. Design: `aidocs/framework/task_relations.md`. **Read D6, D7
(what the agent needs as input) and D13 items 1 and 2.**

This child builds the static candidate generator that feeds the analysis agent,
and runs the two offline measurements that gate turning analysis on.

It **depends on t2192** (the framework shim over the `aitasks_go#93`
task-query engine, with a Python fallback). Task-id backlinks, path citations,
cards and text search come from that shim's verbs; do not build a second
scanner. Read t2192's landed interface, and `aitasks_go#93`'s
`goengines/README.md` *Interfaces* mirror, before planning. The verb names in
this file are the proposals from the 2026-11-04 analysis
(`aidocs/framework/task_search_analysis.md`) and may have changed.

It also depends on t1981_3, whose `ait relations analyze --dry-run` runs the
D13.2 pipeline replay.

## Scope

1. **`.aitask-scripts/lib/relation_candidates.py`** + **`aitask_relation_candidates.sh
   <id> [--json]`**: candidates for one source task.
   - The universe is pending tasks (Ready, Editing, Implementing, Postponed),
     minus the source and folded tasks.
   - Source tags, all from D6:
     - `mention_out` / `mention_in` and `inbox_note`, from the shim;
     - `family`;
     - `meta:<field>` (depends both ways, anchor, verifies,
       children_to_implement, risk_mitigation_tasks, folded_*, follow-up
       origin);
     - `trail`, via `lib/trail_discovery.py`;
     - `cites`, from the shim, with a `hub` flag at
       `parallel_admission.HUB_THRESHOLD`;
     - `line_anchor`;
     - `inflight_overlap`, from `parallel_admission` OVERLAP rows;
     - `token`, from the shim `search` over distinctive tokens of the source;
     - `label_rare` (fan-in < 40).
   - Ordering only, never a relevance cutoff (the D6 order). Full cards up to
     `candidate_cap`. The rest are listed as `TRUNCATED:<n>`, ids grouped by
     source class.
   - Coverage: a provider failure or a missing core verb (mentions, cites) is an
     error, never an empty result. A missing optional verb is listed in
     `coverage.missing_sources`.
   - Grammar gaps go to t2192 / `aitasks_go#93`. No private path grammar.
   - D13.2 also measures whether the cap truncates real recipients (the
     hub-heavy refactor case).
   - Pass the shim's `PROVIDER:engine|fallback` line through.
   - Output: line protocol + `--json`, each candidate with its card and its
     evidence rows.
2. **Static fallback mode** for Step 8e (D8). A flag that restricts the
   universe to push-eligible targets, given a changed-path list: targets that
   are Implementing, or that hold a plan citing a changed path. Rows are
   `UNCONFIRMED:<to>|<sources>|<changed paths cited>`. t1981_5 calls it.
3. **D13.1 candidate replay.**
   - Re-run the seed's Appendix A.1 (`ait attach get 1981
     task_relations_proposal.md`) over this generator's output, **task bodies
     only**: plans leak recipients.
   - Report recall and candidates per sender. Compare with `aitasks_go#93`'s
     numbers for the same replay.
4. **D13.2 offline pipeline replay** (needs t1981_3).
   - Run `ait relations analyze --dry-run` on at least 10 historical senders
     with at least 4 notes each.
   - Use the sender's body and plan as of its plan-approval commit (task-data
     history), and candidates as of today. State the post-hoc caveat.
   - Report recall against the actual recipients, the relation count, the
     PUSH/PULL split, and tokens, cost and wall time per job.
   - **Write the report into this child's plan** (Final Implementation Notes).
     Enabling the layer in this repository is the user's decision on that
     report.

## Key files

- New: `lib/relation_candidates.py`, `aitask_relation_candidates.sh`, a replay
  script (`tests/` or `.aitask-scripts/relations/replay/`), tests.
- Read: t2192's shim script, `lib/trail_discovery.py`,
  `lib/parallel_admission*.py`, `lib/followup_origin.py`, `lib/task_yaml.py`.

## Reference patterns

- `lib/parallel_admission_collect.py`: the in-flight surface and OVERLAP rows,
  and `HUB_THRESHOLD`.
- `lib/trail_discovery.py`: `discover_trails`, `trail_entry_refs`.
- The seed's Appendix A.1 script: the replay mechanics.

## Implementation plan

See `aiplans/p1981/p1981_2_relation_candidate_generator.md`.

## Verification

- Fixture-corpus tests for every source tag, the ordering, the cap and
  `TRUNCATED`, `PROVIDER` pass-through, and both the engine and the fallback
  provider.
- The fallback-mode restriction.
- The two replay reports present in the plan.
