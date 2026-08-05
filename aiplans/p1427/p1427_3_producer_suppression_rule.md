---
Task: t1427_3_producer_suppression_rule.md
Parent Task: aitasks/t1427_reject_shadow_concerns_suppress_next_round.md
Sibling Tasks: aitasks/t1427/t1427_1_rejection_store_helper.md, aitasks/t1427/t1427_2_picker_reject_tristate.md, aitasks/t1427/t1427_4_rejection_docs.md
Archived Sibling Plans: aiplans/archived/p1427/p1427_*_*.md
Worktree: . (current directory — profile 'fast', no worktree)
Branch: main (current branch)
Base branch: main
Output branch: main
---

# p1427_3 — Producer-side rejection-suppression rule + drift guards

Teaches all four shadow concern producers to consult the t1427_1 rejection
store before emitting their concern block, with a propagated inline rule and
the same drift-guard machinery that protects the region rules. Depends on
t1427_1 (helper) and t1427_2 (rejections being persisted).

## Why inline in every producer

Shadow Step 2 (context fetch) is explicitly optional — a producer can run a
whole round without it — so a context-fetch-only delivery has an unreachable
trigger. Precedent: the short-region rule is inlined in each producer because
"these are prompt files read at runtime, and an extra file read is a rule the
agent may skip" (`tests/test_concern_parser.py` docstring).

## The rule (common wording — must contain BOTH guard substrings verbatim:
"previously-rejected" and "aitask_shadow_rejected.sh list")

> **Consult the rejection store before emitting.** If a source task id is
> known (Step 2), run
> `./.aitask-scripts/aitask_shadow_rejected.sh list <task_id>`. Drop any
> fresh concern that is substantively the same as a previously-rejected
> entry, even when reworded. Whenever N ≥ 1 were dropped, report
> `Suppressed N previously-rejected concern(s).` in the prose before the
> block. When unsure whether a fresh concern matches a rejected one, keep it
> and say why (fail-open). When no task id is resolved, state that rejection
> suppression was skipped.

## Steps

1. **`concern-format.md`** (`.claude/skills/aitask-shadow/`): new
   `## Rejected-concern suppression` section (after the trigger-vs-action
   table, before "Where it lives"): store path
   `.aitask-shadow/<task_id>/rejected.md`, the helper `list` call, semantic
   (not hash) matching rationale, fail-open contract, the "Suppressed N"
   report, and a provenance note mirroring :59-63: every producer states this
   rule inline and `tests/test_concern_parser.py::TestProducerRejectionSuppressionRule`
   fails the build if one drops it. Do NOT include a contiguous
   open→items→close block example (t1123 parser-live guard).
2. **Four producers** — add the rule in BOTH positions per file:
   - a bolded pre-emit directive at the head of the emit step (stylistic
     precedent: `impl-challenge.md:373`), and
   - a bullet in the "load-bearing for minimonitor's parser" rules list.
   Sites (planning-time line numbers — re-read from HEAD):
   `plan-challenge.md` (rules :71, emit step 6 :53-101);
   `plan-assumptions.md` (:75, step 6 :50-104);
   `plan-diagnose-errors.md` (:64, step 4 :44-88);
   `impl-challenge.md` (:390, emit section :366-436).
   Keep wording identical across all four modulo the surrounding sentence
   flow; both guard substrings must survive markdown wrapping (the predicate
   collapses whitespace).
3. **`SKILL.md.j2` Step 2** (:151-185): one sentence — resolving the source
   task id also enables rejection suppression (producers consult the store
   keyed by it).
4. **Drift guards — `tests/test_concern_parser.py`:**
   - Module-level predicate:
     ```python
     def _states_rejection_suppression_rule(text: str) -> bool:
         flat = " ".join(text.split())
         return ("previously-rejected" in flat
                 and "aitask_shadow_rejected.sh list" in flat)
     ```
   - New `TestProducerRejectionSuppressionRule`, one-for-one mirror of
     `TestProducerRegionRequiredRule` (:870-922): reuse
     `SHADOW_DIR` / `PRODUCER_MARKER` / `KNOWN_PRODUCERS` / `_producers` from
     `TestProducerShortRegionRule` by reference; duplicate
     `test_producer_set_is_the_known_set`; offenders test with an explanatory
     failure message; negative control building synthetic text (asserts
     predicate False, then True after appending the rule — mutates no repo
     file).
   - Extend `TestRenderedShadowDocsKeepTheGuarantees` (:925-1027): the
     rendered-producer rule check (sibling of
     `test_every_rendered_producer_states_both_region_rules` :1015-1022) now
     also asserts the suppression rule in every rendered producer.
5. **Skill-surface hygiene:** the `SKILL.md.j2` edit requires regenerating
   affected goldens in the SAME commit and a clean
   `./.aitask-scripts/aitask_skill_verify.sh` run (see
   `aidocs/framework/skill_authoring_conventions.md`, "Regenerate goldens
   after any `.md.j2` or closure edit"). Producers are plain `.md` (copied
   into rendered variants) — no `.j2` work for them. Producers live ONLY in
   the Claude tree (`concern-format.md` "Where it lives") — no cross-agent
   port tasks.

## Verification

- `bash tests/run_all_python_tests.sh --test-dir tests` — new guard class
  green; negative control demonstrated able to fail (assert-flip during
  development, not committed).
- `./.aitask-scripts/aitask_skill_verify.sh` clean.
- Live: store a rejection for an active task (via the t1427_2 picker or the
  helper), run a shadow plan-challenge round on that task, confirm the
  suppression report line appears and the rejected concern is absent; then
  un-reject and confirm it returns next round.

Post-implementation cleanup, archival, and merge follow **Step 9
(Post-Implementation)** of the task workflow.
