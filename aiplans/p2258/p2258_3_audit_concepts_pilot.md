---
Task: t2258_3_audit_concepts_pilot.md
Parent Task: aitasks/t2258_doc_audience_levels_and_readable_prose.md
Sibling Tasks: aitasks/t2258/t2258_1_*.md, aitasks/t2258/t2258_2_*.md, aitasks/t2258/t2258_4_*.md, aitasks/t2258/t2258_5_*.md, aitasks/t2258/t2258_6_*.md, aitasks/t2258/t2258_7_*.md, aitasks/t2258/t2258_8_*.md
Archived Sibling Plans: aiplans/archived/p2258/p2258_*_*.md
Base branch: main
Output branch: main
---

# t2258_3 — Concepts audit (pilot)

## Context

First application of the level model (t2258_1) and review skill (t2258_2) to
`website/content/docs/concepts/` (25 pages). The pilot's reader reports and
lessons feed the guide before children 4–7. Method: parent plan § "Common audit
method (children 3–7)".

### Pre-phase (risk mitigations)

1. [reader_test_baseline_and_control] Before editing any page, run
   `aitask-doc-review`'s fresh-reader test (`main-concept` persona) on
   `gates.md`, `framework-session.md`, `skill-templating.md`, `attachments.md`,
   `topic-anchoring.md`, `locks.md` and on controls `tasks.md`, `plans.md`.
   Record each report verbatim below under "Reader reports — before". If the
   long pages do not show more guessed terms / unneeded details than the
   controls, stop, tune persona and questions in
   `.claude/skills/aitask-doc-review/SKILL.md`, re-run, and only then continue.

## Steps

1. **Inventory** all 25 pages (lines, depth, type = explanation, verdict,
   violations) into a table in this plan.
2. **Shared-file gate** per page before editing (diff vs HEAD); dirty pages →
   skipped-page ledger.
3. **Restructure the six long pages**, in order: `locks.md` (move the lock
   and merge-mutex outcome tables and recovery ladder to the owning
   workflow/reference — likely `workflows/crash-recovery.md` or a commands page;
   check what already states them before moving), `topic-anchoring.md`,
   `gates.md`, `framework-session.md`, `skill-templating.md`, `attachments.md`.
   For each: what it is / why / how to use / see also; mechanism moved to its
   owner; record moved facts (source → destination#anchor).
4. **Fix the remaining pages'** violations (including field enumerations in
   model pages such as `tasks.md` "What it is").
5. **Review** each edited page with `aitask-doc-review`.
6. **After-reports:** re-run the fresh-reader test on the same eight pages;
   record under "Reader reports — after".
7. **Feed lessons** into the guide's examples/contracts (t2258_1 sections).
8. **Links:** `cd website && python3 check_links.py --build`;
   `python3 check_link_relevance.py` for retargeted links, open every reported
   target.
9. **Ledger close-out:** re-check skipped pages; audit now-clean ones; create
   `audit_deferred_pages_concepts` (child of t2258, `--no-sibling-dep`) for any
   still dirty. Record outcomes in Final Implementation Notes.

## Reader reports — before

(filled during implementation)

## Reader reports — after

(filled during implementation)

## Verification

- Inventory, moved-fact table, before/after reports and ledger outcomes present.
- `check_links.py --build` exits 0.
- Every concept page has `depth:`; `main-concept` pages contain nothing on the
  guide's forbidden list.

## Post-implementation

Step 9 (review, commit `documentation: … (t2258_3)`, archival).
