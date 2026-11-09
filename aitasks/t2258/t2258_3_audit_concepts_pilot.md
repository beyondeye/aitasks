---
priority: medium
effort: high
depends: [t2258_2]
issue_type: documentation
status: Ready
labels: [documentation, web_site, doc_quality]
gates: [risk_evaluated]
anchor: 2258
created_at: 2026-11-09 23:09
updated_at: 2026-11-09 23:09
---

## Context

Child 3 of t2258 — the **pilot audit**. Read the parent task
`aitasks/t2258_doc_audience_levels_and_readable_prose.md` (evidence section:
concept-page violations) and the approved parent plan
`aiplans/p2258_doc_audience_levels_and_readable_prose.md`, in particular the
**Common audit method (children 3–7)** and the Pre-phase step
`reader_test_baseline_and_control`, both binding here. Child 1 put the level
model and prose rules in `aitasks/metadata/doc_update_guide.md`; child 2 built
`.claude/skills/aitask-doc-review/SKILL.md`. This child applies them to
`website/content/docs/concepts/` (25 pages) first, so lessons reach the guide
before the larger audits.

Known violations (measured 2026-11-09): `concepts/locks.md` (main-concept, 127
lines, opens with a 7-row lock-outcome table), `gates.md` (237 lines, 8 `###`),
`framework-session.md` (198), `skill-templating.md` (190), `attachments.md`
(164), `topic-anchoring.md` (main-concept, 141). Models: `tasks.md`, `plans.md`,
`folded-tasks.md`, `execution-profiles.md` (28–80 lines). Even `tasks.md`
enumerates frontmatter fields under "What it is" — check the models too.

## Pre-phase (risk mitigation) — reader_test_baseline_and_control

1. Before restructuring any page, run the fresh-reader test (via
   `aitask-doc-review`, `main-concept` persona) on the six long pages above
   **and** on `tasks.md` and `plans.md` as controls. Record every report
   verbatim in this child's plan.
2. If the reports do not separate the long pages from the controls (more
   guessed terms / unneeded details on the long pages), stop and tune the
   persona and question set in `aitask-doc-review` before restructuring.
3. After restructuring, re-run on the same eight pages and record the
   after-reports (child 8 compares them).

## Method (from the parent plan; summary)

1. Inventory all 25 pages in the plan: lines, `depth`, page type, verdict,
   violations (Diátaxis anti-patterns 1/2/5 first, then 3/4; the guide's level
   contract; the prose rules).
2. Shared-file gate before each edit: diff against HEAD; a page dirty from
   another session is not edited — record it in a **skipped-page ledger**
   (path, reason, dirty state seen). Before closing, re-check each entry; now
   clean → audit it here; still dirty → create a child of t2258 with
   `--no-sibling-dep` named `audit_deferred_pages_concepts` listing pages,
   violations and reason. Final Implementation Notes record each entry's
   outcome (`audited` / `follow-up t2258_<n>`); do not archive otherwise.
3. Restructure: mechanism moves to the page that owns it (workflow, command,
   skill, reference page, or `aidocs/` for contributor-only internals); keep the
   concept page to what / why / how-to-use / see-also. Record every moved fact
   (source → destination#anchor) in the plan.
4. `aitask-doc-review` on each edited page.
5. `cd website && python3 check_links.py --build` (mandatory);
   `python3 check_link_relevance.py` for retargeted links, opening every
   reported target.
6. Rule refinements go back into the guide's examples.

## Verification

- Inventory table, moved-fact table, before/after reader reports and the
  skipped-page ledger outcomes are in the plan.
- `check_links.py --build` exits 0.
- Every concept page has `depth:`; every `main-concept` concept page passes the
  guide's forbidden-content list.
