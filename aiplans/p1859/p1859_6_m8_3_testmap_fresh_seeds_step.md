---
Task: t1859_6_m8_3_testmap_fresh_seeds_step.md
Parent Task: aitasks/t1859_testmap_m8_completion_policy_and_gates.md
Sibling Tasks: aitasks/t1859/t1859_1_*.md, aitasks/t1859/t1859_2_*.md, aitasks/t1859/t1859_3_*.md, aitasks/t1859/t1859_4_*.md, aitasks/t1859/t1859_5_*.md
Archived Sibling Plans: aiplans/archived/p1859/p1859_*_*.md
Base branch: main
Output branch: main
---

# Plan: t1859_6 — M8.3 seeds step of `testmap_fresh` (coarse)

## Context

Parent t1859 (M8); Module Map row **M8.3**, the seeds step (the parent's
Deviation 6 splits it from the base `t1859_3`); wave **G**. When a task touches
a test file that has rows in `seeded.yaml`, the gate reads the engine-cut
packets and either adopts or parks those pairs on verdicts. A map therefore
migrates a few files per task through ordinary work.

This coarse plan records what the proposal fixes for the M8.3 seeds step. It
does not design internals against providers that do not exist yet; the
Reality check below does that when this child is picked.

**Automation-first:** autonomous runs adopt through `onboard adopt
--agent-verdicts -`. `verifies` adopts; `drives` and `unsure` park, and parked
rows keep selecting. The attended confirm / override / trust-batch steps are
UX, never a precondition.

**Dependency hold:** `Postponed` until M7.1 and M7.2 (t1858) have child ids in
`depends:`.

## Proposal reading list

- *The Agent Review Pass* (*The packet*, *The verdict*, *The in-gate site
  (Step 8)*).
- Components *Freshness*, *Skills*, *Agent review verbs*.
- *Data Flow → Level 1*.
- Invariants 2, 3 and 7.
- Parent plan Deviation 6.

## Owned files / provides / consumes

- **Owns:** the seeds step inside `.claude/skills/aitask-gate-testmap-fresh/**`
  (an extension of `t1859_3`'s skill) and its goldens.
- **Provides:** the in-gate reading site. Consumers: M10.1 and M10.3–M10.5
  review loops.
- **Consumes:**
  - the base `t1859_3`;
  - held: M7.1 (`onboard review --ids`, packets) and M7.2 (`onboard adopt
    --agent-verdicts`, the verdict grammar);
  - `aitask_change_surface.sh`.

## Step 0 — Reality check (MANDATORY, before any code; outcome recorded in this plan file)

1. Re-read the in-gate site, the components, and the interface row "review
   packets and the verdict grammar".
2. Inspect the actual state, naming the task and commit for each: M7.1's
   packets, M7.2's intake and its `VERDICT_*` lines, the base skill as landed,
   and M6.5's `review.md` if it has landed.
3. Tabulate *proposal* / *coarse plan* / *repository*.
4. Decide each difference and record it. **Stop if M7.1 or M7.2 has not
   landed.**
5. Send notes to t1861 (M10 review loops) and t1860 (M9.5 ports) where an
   assumption breaks, hedged.
6. Re-confirm ownership.

## Implementation steps (coarse)

1. For each `COMMITTED:` / `TASK:` test file with seeds, run `onboard review
   --ids <rows>` and read the packets.
2. **Attended:** pre-fill the agent's verdict and rationale per row. The
   person confirms (`by: human`), overrides, or trusts the batch
   (`by: agent`).
3. **Autonomous:** `onboard adopt --agent-verdicts - --by <agent-string> --run
   <gate-run-id>`.
4. Make sure the stamps ride the `(t<id>)` commit.
5. Regenerate goldens and run `aitask_skill_verify.sh`.

## Verification / acceptance

- Autonomous `--agent-verdicts` adoption rides the commit, and parked rows
  stay.
- Attended pre-fill, override and trust-batch record `by: human` / `by: agent`.
- No stamp is written without a `verifies` verdict.
- `aitask_skill_verify.sh` is green.
- No path requires a human action.

## Step 9 reference

The shared post-implementation flow: current branch, no merge.
