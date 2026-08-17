---
Task: t1544_8_backlog_stats_retrospective.md
Parent Task: aitasks/t1544_stats_backlog_and_net_flow_by_category.md
Sibling Tasks: aitasks/t1544/t1544_1_*.md, aitasks/t1544/t1544_2_*.md, aitasks/t1544/t1544_3_*.md, aitasks/t1544/t1544_4_*.md, aitasks/t1544/t1544_5_*.md, aitasks/t1544/t1544_6_*.md, aitasks/t1544/t1544_7_*.md
Archived Sibling Plans: aiplans/archived/p1544/p1544_*_*.md
Base branch: main
Output branch: main
---

# p1544_8 — Backlog stats retrospective

## Goal

Evaluate the design commitments t1544 made under partial information, and file
standalone follow-ups **only where the collected data justifies them**. Per
`aidocs/framework/planning_conventions.md`, an evaluation with no findings
produces an evaluation-only record, not speculative infrastructure —
"no change needed" is the expected outcome for most questions here.

This task writes **no production code**.

## Method

1. Re-measure everything against the corpus **at the time of writing**. Do not
   copy the parent plan's planning-time snapshot: the corpus moved measurably
   during planning alone (the live population went 416 → 420 in about an hour,
   and an archived task landed mid-measurement).
2. Read the eight sibling tasks' Final Implementation Notes — several questions
   below are answered directly by what the implementers recorded.
3. Answer each question in the task body under a `## Retrospective findings`
   heading in **this plan file**, one subsection per question.
4. End every subsection with an explicit disposition: **no change needed**,
   **filed as tN**, or **folded into tN**.

## Questions

The full list, with the reasoning behind each commitment, is in the task body
(`aitasks/t1544/t1544_8_backlog_stats_retrospective.md`). In summary:

1. Was **flows-only storage** the right shape — did anyone want a stored level,
   did the O(k) cumulation stay cheap, did the `out_offsets`-selects-columns-only
   contract survive a second caller?
2. Is **8 weeks** the right default horizon — is it routinely overridden, does it
   truncate the interesting part of the trend? If the TUI wants a different
   value, that is a *user setting applied to both surfaces*, never a second
   literal.
3. Is **parent + child** the right denominator — does the `(parents / children)`
   split do its job?
4. Was counting **Postponed as open** the right call at today's counts?
5. Did the **TUI presentation** hold up at real cardinality (17 categories, the
   row cap, the netflow category split)? This was the plan's main unproven risk.
6. Did the **doubled `collect_stats` cost** matter in practice — measure
   `ait stats-tui` startup with the real number of registered repos; was
   `with_backlog=False` on `work_report_gather` enough; is the deliberately
   out-of-scope no-live-walk opt-out now worth filing?
7. Did the **two completion clocks** confuse anyone, or did the footnote work?
8. Deferred items that may now be worth filing: the preset **list-replacement**
   semantics t1544_5 pinned but did not change; `week_start` / `days` in
   `stats_config` being persisted but never read (needs `resolve_week_start`
   moved to `lib/` first — existing TODO t597_4); whether `created_at` on the
   per-task CSV is actually used.

## Files

- `aiplans/p1544/p1544_8_backlog_stats_retrospective.md` — this file, extended
  with `## Retrospective findings`
- New task files only where a finding justifies one

## Verification

- Every question has a written answer with an explicit disposition.
- Any follow-up task created is referenced by ID in the findings.
- Every number quoted in the findings was re-measured, not copied from the
  parent plan.
