---
Task: t832_6_retrospective_dogfooding_evaluation.md
Parent Task: aitasks/t832_brainstorm_cross_repo_skills_retrieval_xdeps_parallel_planni.md
Sibling Tasks: aitasks/t832/t832_*_*.md
Archived Sibling Plans: aiplans/archived/p832/p832_*_*.md (after others land)
Worktree: aiwork/t832_6_retrospective_dogfooding_evaluation
Branch: aitask/t832_6_retrospective_dogfooding_evaluation
Base branch: main
---

# Plan: retrospective dogfooding evaluation

See parent plan §t832_6. Depends on all other t832 children landing.

## Goal

Drive a real coordination task between `aitasks` and `aitasks_mobile`
end-to-end using the now-shipped plumbing. Document what worked, what
surfaced friction, and file targeted follow-ups.

Per `aidocs/planning_conventions.md` audit-only rule: zero findings →
deliverable is the documented audit, no follow-ups.

## Implementation steps

1. **Identify a real cross-repo coordination need** (candidates):
   - Applink wire-protocol bump spanning aitasks + aitasks_mobile.
   - Shared schema change for QR-pairing payload.
   - The historical t13_2-style "sister QR add hostname field" pattern,
     if it's still relevant.

2. **Use the parallel-planning procedure (t832_5)** to design the paired
   decomposition. Capture friction in real-time as you exercise each
   shipped surface:
   - **t832_1 (`--project` on query helpers):** any subcommands that
     felt awkward? Re-exec contract surprises?
   - **t832_2 (explain context cross-repo):** unified-markdown
     aggregation work as expected?
   - **t832_3 (xdeps parser + create-time validation):** did the
     validation catch real mistakes? False positives?
   - **t832_4 (xdeps blocking):** did UNREACHABLE fire when expected?
     Was Done-only too restrictive in practice?
   - **t832_5 (parallel-planning procedure):** numbering-lockstep
     race conditions? Commit-ordering failures? Driver-symmetry
     ambiguity?
   - **t832_7 (cross-repo update):** lock guardrails fire correctly?
     Status-transition allowlist too restrictive?
   - **t832_8 (board cross-repo display + navigation):** read-only
     popup sufficient, or do users want a full project-switch?
     Notation parser activation feel right?
   - **Notation gap:** is the `aitasks#N_M` notation actually used by
     humans, or is everything going through `xdeps:` / `xdeprepo:`?

3. **Implement the chosen coordination task end-to-end** across both
   repos. Track each tool invocation that produced friction.

4. **Author the audit document** at
   `aidocs/cross_repo_retrospective_t832.md`:
   - Section per shipped surface (t832_1, t832_2, ...).
   - "What worked" subsection with concrete examples.
   - "What surfaced friction" subsection with reproducers.
   - "Recommended follow-ups" listing each suggested task by name,
     scope, and the friction it addresses.

5. **File targeted follow-up tasks** for confirmed friction. Likely
   candidates:
   - `ait monitor` cross-repo surfacing (deferred from t832).
   - Board project-switch (if popup proves insufficient).
   - xdeps maintenance / repair (if stale refs surface during testing).
   - Cross-repo `--fold` (if folding semantics become needed).
   - Auto-clone from `git_remote` on NOT_FOUND (t826_5 scope).

   Each follow-up is a top-level aitask (NOT a child of t832).

## Verification

- `aidocs/cross_repo_retrospective_t832.md` exists with all sections
  populated.
- Each filed follow-up task body references this retrospective and the
  specific friction it addresses.
- If zero friction: the audit document explicitly states "no follow-ups
  needed" and the deliverable is the audit alone.

## Notes

- The retrospective is observational. Do NOT expand scope to fix
  friction in this task — file separate follow-ups instead.
- Keep the audit document concise; bullet-style is fine.

## Out of scope

- Re-implementing siblings.
- Major refactors driven by findings (file as follow-ups).

## Final Implementation Notes

(To be filled by the implementing agent during/after execution.)
