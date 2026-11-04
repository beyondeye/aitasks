---
Task: t1981_5_relations_consumption.md
Parent Task: aitasks/t1981_task_relations_and_obsolescence_design.md
Sibling Tasks: aitasks/t1981/t1981_1_relations_store_and_cli.md, aitasks/t1981/t1981_2_relation_candidate_generator.md, aitasks/t1981/t1981_3_relations_worker_and_analysis.md, aitasks/t1981/t1981_4_relations_triggers.md, aitasks/t1981/t1981_6_obsolescence_layer.md, aitasks/t1981/t1981_7_relations_tui.md, aitasks/t1981/t1981_8_relations_website_docs.md, aitasks/t1981/t1981_9_port_relations_skill_changes.md, aitasks/t1981/t1981_10_relations_retrospective.md
Archived Sibling Plans: aiplans/archived/p1981/p1981_*_*.md
Base branch: main
Output branch: main
---

# t1981_5 — Relations consumption: related-work check, Step 8e, /aitask-note

## Context

The consumer side of `aidocs/framework/task_relations.md` D8: the hybrid model,
pull by default and push narrowly. It depends on t1981_1 (the store) and t1981_3
(`analysis-state`). The static fallback calls t1981_2's fallback mode when that
is present, and reports "unavailable" otherwise.

## Steps

0. **Reality check.**
   - Re-read D8 in full and D11.
   - Re-read task-workflow Step 3. **t1663_4** plans a premise check as "Check
     6", but Check 6 is the Inbox check. Whichever lands second takes the next
     number. Coordinate with t1663_4 if it is in flight.
   - Re-read Step 8 and Step 8e, and `aitask-note/SKILL.md`'s no-target path.
   - Re-read `related-task-discovery.md` and any **t2192** edits to it. This
     task adds store-first ahead of it and owns Step 8e.
1. **`notify-candidates`** in `aitask_relations.sh`, backed by a function in
   `lib/relations_store.py` or in a new `lib/relations_consume.py`. Implement
   D8's push rules exactly:
   - derive S's change set from its commits with `(t<S>)` in the subject,
     reachable from HEAD. `--diff <range>` overrides;
   - read relations(S) and keep the pending targets;
   - validate the impact bases against the change (the changed files with the
     `-M` rename map, read with `-z`; symbols and tokens in the hunks). A
     `task_ref` never confirms impact;
   - the direction guard: `affects` needs `from = S`; `coordinates_with`
     accepts either end;
   - the target-state check: Implementing, or a plan (file or
     `plan_approved_at`);
   - the current-citation check: the target's current body or plan still cites
     a confirmed basis, otherwise PULL `target_moved`;
   - emit `PUSH:` and `PULL:<reason>` rows; nothing is discarded;
   - expose the confirmation function, so that pull can recompute confirmation
     for a landed task L from L's own `(t<L>)` commits.
2. **The related-work procedure** (new):
   `.claude/skills/task-workflow/related-work-check.md`, with two entry points.
   - The Step 3 check, after Check 6. It reads `ait relations show <id>` and
     groups as D8 describes: landed since the reference time (direction-filtered),
     in flight now, this task's own relations. It is display only, at most 8
     items, and hands the list to planning as context.
   - The Step 8 entry, before the review prompt: relations whose other side
     landed after the pick, and relations published after the pick-time check.
     It marks "covered by note <id>" through `aitask_query_files.sh inbox`.
   - Both entries render the state lines in plain words.
3. **Step 8e** in `SKILL.md`:
   - call `analysis-state <S> --expect-plan <relations_expected_plan>` first.
     The variable is set by t1981_4's Step 7 `stamp` call, or by Re-entry
     Routing's `plan-digest`. When it is missing, omit the flag, and the state
     reads `unverifiable(no_expected_identity)`;
   - on `complete`, run `notify-candidates` and offer a note for each PUSH row
     (multi-select, never automatic), pre-filled with the description and the
     matched diff evidence; the agent first checks that the description still
     matches what landed;
   - on an incomplete state, show it, then offer wait / static fallback /
     proceed. At the cap, `wait` needs a second explicit confirmation and
     `--over-cap`;
   - with nobody to answer, the profile key `relations_incomplete_action`
     decides (`ask` default / `wait` / `fallback` / `proceed`). Document it in
     `profiles.md`;
   - when disabled, say so, keep today's judgement offer, and offer the static
     fallback as an optional aid;
   - keep today's judgement offer for findings that do not come from relations.
4. **`/aitask-note` with no target**: relations(sender) first, then the Related
   Task Discovery Procedure.
5. **Ledgers.** `pull.jsonl` and `notify.jsonl` under
   `<git-common-dir>/aitask-relations/`, with the D13.3 fields. Appends are
   atomic (one line, `O_APPEND`).
6. **Goldens.** Regenerate them for every changed `.md.j2` or procedure, and run
   `aitask_skill_verify.sh`.

## Verification

Fixture records and diffs:
- the three direction cases (forward-only, reverse-only, symmetric);
- a task-ref-only relation → PULL `unconfirmed_impact`;
- a target that no longer cites the basis → PULL `target_moved`;
- change-set derivation in both current-branch and worktree mode;
- "landed" excludes superseded and obsolete archives;
- an unrelated landing → PULL;
- every incomplete state, including the cross-host `inputs_mismatch`, and
  `unverifiable` for a missing stamp or a stale store; none yields "no affected
  targets";
- the disabled wording at all four surfaces;
- the Step 8 re-check shows a late-published relation, and marks one covered by
  a note;
- the goldens regenerated;
- `shellcheck`.

## Step 9

Post-implementation per task-workflow Step 9. Ports are t1981_9.
