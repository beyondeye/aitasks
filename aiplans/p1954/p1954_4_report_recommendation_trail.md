---
Task: t1954_4_report_recommendation_trail.md
Parent Task: aitasks/t1954_research_multilanguage_annotation_parsers.md
Sibling Tasks: aitasks/t1954/t1954_1_*.md, aitasks/t1954/t1954_2_*.md, aitasks/t1954/t1954_3_*.md
Archived Sibling Plans: aiplans/archived/p1954/p1954_*_*.md
Base branch: main
Output branch: main
---

# Plan: t1954_4 — Report, recommendation, trail and follow-ups

## Context

Final child of t1954: the synthesis. The parent task's **Deliverables and
trail integration** and **Acceptance criteria** sections are binding. Read:
- the parent task;
- the parent plan `aiplans/p1954_research_multilanguage_annotation_parsers.md`;
- the archived plans of t1954_1–3;
- `R/findings_t1954_{1,2,3}.md` and `R/results/*`, with
  `R = aidocs/testing_engine/t1954_parser_research/`.

## Step 0 — reality check

- `git log -1 -- goengines/internal/testmap/annot` vs `R/baseline/PIN`.
- Pull the latest trail (`./ait artifact get art:trail-testmap-feature`) and
  the topic membership
  (`./.aitask-scripts/aitask_trail_gather.sh snapshot --scope topic 1852`).
- Resolve the consumer child IDs as they exist now.

## Steps

1. **Final rerun**: one environment, every provider, using the README
   commands. Refresh `R/results/environment.md`.
2. **Post-phase (risk mitigations)**
   1. [baseline_rerun_at_landed_commit] If annot moved past the PIN, run the
      baseline at both commits (move the pin in a committed edit; keep the old
      results file), report both columns, and name every differing case.
   2. [native_oracle_gap_followup] For each language still at `native: none`,
      claim nothing beyond the hand-oracle evidence in the policy, and create
      one bounded follow-up (anchor 1852) to validate on a host with the
      compiler.
3. **Report** `aidocs/testing_engine/t1954_annotation_parser_research.md`,
   with these sections:
   - Summary and decision
   - Method (corpus, seam, metrics, environment, reproducibility)
   - Candidate matrix, safety columns first, every family
   - Per-family evaluation: observations, documentation claims, assumptions
     and unknowns kept separate
   - Rejected alternatives with evidence
   - Dependency, licensing and maintenance analysis
   - Recommendation, or an explicit no-candidate-yet conclusion
   - Language policy: supported / experimental / unsupported, with the
     evidence behind each tier
   - Provider/adapter contract: comment locations, uncertainty, safe
     placement, onboarding policy, conformance fixtures
   - Migration sketch with an implementation-complexity comparison (no
     schedules)
   - Impact on M2.2's rewriter, conflicts, root confinement/no-follow,
     stamp/provenance, and the annotate/verify/stale/adoption/author/repair
     flows
   - Residual risks
   - Evidence index: paths and artifact handles
4. **Evidence artifact**: tar the raw logs (not committed) and run
   `./ait artifact create 1954 <bundle> --kind research_evidence`. Put the
   handle in the report's evidence index.
5. **Trail refresh**: follow the `aitask-trail` skill's refresh procedure at
   **deep** depth for `art:trail-testmap-feature`.
   - Replace the e-parser-research entry's "no result yet" with the decision,
     the exact report path and the evidence handle.
   - Add the evidence entries and relations.
   - Place the new follow-ups with advisory ordering.
   - Record residual risks and affected modules.
6. **Consumer evaluation**: t1853_2 (landed), t1853_3, t1855, t1857, t1858,
   t1853_7, t1860, t1861 and t1863, using their actual child IDs. Give each
   an action or context-only verdict, in a table in the report.
7. **Follow-ups and notes**
   - Create the bounded implementation follow-ups the recommendation justifies
     (`aitask_create.sh --batch --commit --anchor 1852`). Use hard `depends`
     only for real prerequisites.
   - Send advisory notes with the report link and decision to the affected
     existing tasks via the `/aitask-note` skill (`--from 1954_4`).
8. **Link check**: every path and handle cited by the report and the trail
   resolves (`test -e`, `./ait artifact versions <handle>`).

## Verification

- The report exists at the exact path.
- The trail has a new version that names the report and the handle.
- The follow-ups carry `anchor: 1852`.
- Every note returns `NOTE_APPENDED:`.
- Commits are path-scoped: the report and `R` paths via `git`, task and plan
  files via `aitask_task_commit.sh`.

## Step 9 reference

`documentation: … (t1954_4)` commit for the report; standard child archival.
The parent t1954 archives with this last child.
