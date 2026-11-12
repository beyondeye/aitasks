---
priority: low
effort: low
depends: [t1912_6]
issue_type: chore
status: Ready
labels: [git, concurrency, verifiedstats]
gates: [risk_evaluated]
anchor: 1599
created_at: 2026-11-12 19:43
updated_at: 2026-11-12 19:43
---

## Context

Child 7 of t1912: the retrospective evaluation. Parent plan:
`aiplans/p1912_move_codeagent_stats_to_plumbing_branch.md`. Depends on
t1912_1-6. **Run it only after roughly two weeks of normal multi-agent use
following the landing of t1912_4 and t1912_5.** If picked earlier, check the
landing dates and offer "Approve and stop here".

t1912 moved code-agent stats commits off `aitask-data`, so that a stats
update no longer opens rebase / fast-forward windows on the shared
`.aitask-data` worktree.

Baseline from t1912's Evidence section, one machine's `.aitask-data` reflog,
2026-06-28 → 2026-10-07:

| Measure | Value |
|---|---|
| Rebase cycles | 307 |
| Rebase cycles where origin's extra commits were only stats commits | 269 (88%) |
| Rebase cycles that included any stats commit | 294 (96%) |
| Fast-forward converges | 282 |
| Fast-forward converges with only stats commits | 275 |

## Pre-registered investigation

1. Replay the `.aitask-data` reflog from the t1912_4 landing date onward,
   using the same method as the Evidence section:
   - replay each `(start)` rebase with
     `git merge-tree --write-tree <onto> <orig-head>`;
   - classify each cycle's remote-only commits by subject (`Update usage
     count` / `Update verified score`, and the new migration
     `Stats-Migration-*` trailers);
   - count fast-forward converges the same way.
2. Report:
   - the rebase cycles and fast-forward converges whose remote-only commits
     are stats commits. **Expected: none**, unless another machine was still
     on an older framework (identify it by author or host);
   - the `aitask-stats` branch: commit count, retries observed (if logged),
     and the per-agent marker states;
   - any `STATS_DIVERGED` / `MIGRATE_DEFERRED` / `STRIPPED_RESIDUE`
     occurrences.
3. Decision rule:
   - If expected ⇒ record the outcome and create no follow-ups.
   - If not ⇒ file one standalone follow-up per distinct cause, with the
     evidence.

## Verification

The report, its numbers, and the exact commands used go into the plan's
Final Implementation Notes, verbatim, so they are reproducible.

Step 9 (Post-Implementation) applies.
