---
priority: low
effort: medium
depends: []
issue_type: enhancement
status: Ready
labels: [shadow]
gates: [risk_evaluated]
anchor: 1158
created_at: 2026-07-21 12:25
updated_at: 2026-07-21 12:25
boardidx: 10
---

## Origin

Risk-mitigation ("after") follow-up for t1200, created at Step 8d after
implementation landed.

## Risk addressed

Goal-achievement risk 2 from `aiplans/archived/p1200_*.md`:

> By deliberate decision, Default keeps its one-pass three-axis methodology and
> its two self-suppressing axes (S1 "do not re-flag an addressed risk", S2 "only
> unexplained deviations"). Removing the omit-by-default clause and adding
> anti-drop may therefore only **partially** lift Default's finding volume — some
> of the user's symptom may be inherent to the legacy methodology, and the real
> remedy would be "use Advanced" · severity: medium

## Goal

t1200 fixed the two *mechanical* suppressors in the shadow implementation review:
the disposition rubric's "omitted by default" clause for accepted/deferred risks,
and the anti-drop rule not reaching the Default tier. What it deliberately did
**not** touch is Default's methodology itself — one full-context pass over three
axes, two of which (S1, S2) are self-suppressing by construction.

So the original symptom ("running the Default review very rarely yields any
concerns") may only be partially resolved. This task closes that loop.

**After a period of live use:**

1. **Measure.** Compare Default-tier review output before and after t1200 on
   comparable diffs. Does finding volume actually recover, or does it stay low?
   The manual-verification task **t1202** produces the first live datapoint —
   read its results before starting here.
2. **Diagnose, if still low.** Determine whether the remaining suppression comes
   from the legacy methodology itself (single pass, no candidate fan-out, no
   verdict ladder to adjudicate half-believed candidates, S1/S2 narrowness) or
   from some other instruction still steering the reviewer toward silence.
3. **Decide and implement one of:**
   - **Promote Advanced as the routed default** — an unqualified "adversarial
     review" would resolve to Advanced instead of Default. t1200 already added
     the inferred-tier announcement, so the routing change is small; the cost is
     breaking the documented "Default = legacy, preserved" compatibility
     contract in `impl-challenge.md` and the website workflow doc.
   - **Retire the Default tier** — collapse to quick / advanced / deep if the
     legacy tier has no remaining constituency.
   - **Strengthen Default in place** — e.g. give it a lightweight verdict ladder
     so half-believed candidates are adjudicated rather than judged by gut.
     Note this also breaks the "preserved one-to-one" claim.
   - **Keep as-is** — if measurement shows Default recovered, record the
     evidence and close.

Whichever option is chosen, update `impl-challenge.md`, `aitask-shadow/SKILL.md`,
and `website/content/docs/workflows/shadow-agent.md` together, and re-run
`tests/test_shadow_disposition_surfaces.py` (the t1200 drift guard).

## Key files

- `.claude/skills/aitask-shadow/impl-challenge.md` — tier definitions, the tier
  auto-detect table, the inferred-tier announcement.
- `.claude/skills/aitask-shadow/impl-review-angles.md` — Angles S0/S1/S2, the
  anti-drop rule, the verdict ladder.
- `website/content/docs/workflows/shadow-agent.md` — user-facing tier docs.
- `tests/test_shadow_disposition_surfaces.py` — drift guard; its `SITES` table
  must stay in sync if headings move.

## Notes

- Do **not** start this before **t1202** (manual verification of t1200) has been
  run — its output is the evidence this task depends on.
- The shadow sub-procedure files live only in the Claude tree; `.agents/` and
  `.opencode/` carry a `SKILL.md` wrapper only, so no cross-agent port is needed
  for changes confined to these files.
