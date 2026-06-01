---
priority: medium
effort: low
depends: [t832_1, t832_2, t832_3, t832_4, t832_5, t832_7, t832_8]
issue_type: feature
status: Implementing
labels: [cross_repo, retrospective]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-05-26 18:28
updated_at: 2026-06-01 12:19
---

## Context

Part of t832 brainstorm decomposition. Drive a real coordination task
between `aitasks` and `aitasks_mobile` end-to-end using the now-shipped
cross-repo plumbing (siblings t832_1 through t832_5, t832_7, t832_8).
Document outcomes; file targeted follow-up tasks for confirmed friction.

This is a retrospective-evaluation child per `aidocs/planning_conventions.md`:
"When committing to a design choice under partial information, proactively
propose the retrospective-evaluation child."

## Key Files / Surfaces to Exercise

- `aitask_query_files.sh --project <name>` (t832_1)
- `aitask_explain_context.sh --project <name>:<file>` (t832_2)
- `xdeps:` / `xdeprepo:` task creation (t832_3)
- Cross-repo blocking display in `aitask_ls.sh` (t832_4)
- `parallel-cross-repo-planning.md` procedure (t832_5)
- `aitask_update.sh --project <name>` (t832_7)
- `ait board` cross-repo display + navigation (t832_8)

## Implementation Plan

1. Identify a concrete coordination need between `aitasks` and `aitasks_mobile`
   (e.g., a wire-protocol bump, a shared schema change, or revisit the
   t13_2-style "sister QR add hostname field" pattern).
2. Use the parallel-planning procedure (t832_5) to design the paired
   decomposition. Capture every friction point in real-time:
   - Numbering-lockstep race conditions or surprises.
   - Commit-ordering rough edges (cross-repo push failures, partial rollback needs).
   - `xdeps` blocking UX in the board (t832_8) — does the read-only popup
     navigation carry its weight, or do users want a full project-switch?
   - Re-exec contract: any unanticipated subcommand shapes that needed bespoke handling?
   - Notation gap: does the `aitasks#N_M` notation parser carry its weight,
     or are `xdeps:` / `xdeprepo:` doing all the load-bearing work in
     practice?
3. Implement the chosen coordination task end-to-end across both repos.
4. Author an audit document at `aidocs/cross_repo_retrospective_t832.md`
   summarizing:
   - What worked (with examples)
   - What surfaced friction (with reproducers)
   - Recommendations for follow-up tasks (be specific: file path, suggested
     scope, why it matters)
5. File targeted follow-up tasks for confirmed friction (e.g., `ait monitor`
   cross-repo surfacing if the gap bites; xdeps maintenance/repair if stale
   refs surface; board project-switch if the popup model proves insufficient).

## Verification Steps

- Audit document `aidocs/cross_repo_retrospective_t832.md` exists and is
  comprehensive (covers each numbered area in the Implementation Plan).
- Each filed follow-up task references the specific friction it addresses
  and links back to this retrospective.
- If no friction surfaces, the deliverable is "documented audit + no
  follow-ups needed" per the `audit-only` planning convention.

## Notes for sibling tasks

- The follow-up tasks filed here may include: `ait monitor` cross-repo
  surfacing (deferred from t832), board project-switch (deferred from
  t832_8), and any genuinely new gaps that only surfaced during dogfooding.
- Each follow-up should be a top-level aitask (not a child of t832 — t832
  is then "Done").

## Out of scope

- Re-doing the work of siblings t832_1 through t832_5 / t832_7 / t832_8 —
  this task is observational, not implementation.
- Major refactors driven by dogfooding findings — file as separate
  follow-up tasks instead of expanding scope here.

See parent plan §t832_6 for the full design context.
