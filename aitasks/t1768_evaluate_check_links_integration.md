---
priority: low
effort: medium
depends: []
issue_type: enhancement
status: Ready
labels: [documentation, website]
gates: [risk_evaluated]
anchor: 1661
followup_kind: risk_mitigation
created_at: 2026-09-09 15:49
updated_at: 2026-09-09 15:49
---

## Origin

Risk-mitigation ("after") follow-up for t1759, created at Step 8d after implementation landed.

## Risk addressed

Addresses goal-achievement risk 3 of t1759's plan:

> Coverage is limited to backtick-quoted link text (~360 of ~500 internal
> links); prose link text and shortcode-generated links stay invisible ·
> severity: medium

## Goal

Now that `website/check_link_relevance.py` exists and one sweep has been read,
decide two deferred questions t1759 could not answer before it had a report:

1. Is any part of the relevance heuristic precise enough to fold into
   `website/check_links.py` as a **non-blocking warning**?
2. Should coverage widen past backtick-quoted link text?

## Concrete input from t1759's sweep

The first sweep reported **4 links, all false positives**, in three classes:

| record | class |
|---|---|
| `docs/tuis/monitor/how-to.md:236` `` `ait minimonitor` `` → `minimonitor/how-to/#how-to-mark-an-agent-as-prioritized` | subject-of-page paraphrase |
| `docs/workflows/crash-recovery.md:30` `` `aitask_lock.sh` `` → `/docs/commands/lock/` | implementation-name link text vs. user-facing command page |
| `docs/workflows/parallel-development.md:44` `` `/aitask-pick` `` → `/docs/skills/aitask-pick/parallel-admission/` | sub-page of the named command's own doc section |
| `docs/workflows/risk-evaluation.md:38` `` `ait board` `` → `board/reference/#task-metadata-fields` | subject-of-page paraphrase |

**A candidate refinement, measured but deliberately not applied in t1759.**
All four share a shape: the stemmed token appears in the **target's own URL
path** (`minimonitor`, `lock`, `aitask-pick`, `board`). Neither t1707 instance
does — `ait artifact` → `/docs/commands/task-management/` and
`/docs/workflows/implementation-trails/`. So a "token in target path ⇒ hit"
rule would clear the report to zero while preserving both known true positives.

t1759 declined to implement it on purpose: tuning the heuristic against the
four records it had just produced, to make its own output look clean, is
exactly the "tuned to the known instances" risk t1759 inherited from t1707.
**One sweep is not evidence that a suppression rule generalizes.** This task
should decide it against more than one sweep, and must keep the t1707 fixtures
(`KnownClassControlTests`) passing whatever it does.

## Constraints inherited from t1759

- The report **never gates**. If any part moves into `check_links.py`, it must
  be a non-blocking warning — `check_links.py` gates the deploy, and a
  heuristic with a known false-positive rate must not be able to block it.
- The two scripts own different questions and different inputs (built HTML vs.
  markdown sources). See the division-of-labour table in `website/README.md`;
  do not let either grow into the other's job.
- `scope_narrowed_verdict` (reported as `scope-narrowed`) already isolates the
  "token is on the page, just not in that section" false-positive shape — a
  ready-made lever if a class-specific suppression is wanted.

## Reference

- `website/check_link_relevance.py` — the detector and its self-controls.
- `tests/test_check_link_relevance.py` — 48 tests; the t1707 positive/negative
  control pair is the acceptance floor for any precision change.
- `aiplans/archived/p1759_*.md` — full design rationale and triage table.
