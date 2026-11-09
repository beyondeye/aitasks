---
Task: t2258_4_audit_workflows.md
Parent Task: aitasks/t2258_doc_audience_levels_and_readable_prose.md
Sibling Tasks: aitasks/t2258/t2258_1_*.md, aitasks/t2258/t2258_2_*.md, aitasks/t2258/t2258_3_*.md, aitasks/t2258/t2258_5_*.md, aitasks/t2258/t2258_6_*.md, aitasks/t2258/t2258_7_*.md, aitasks/t2258/t2258_8_*.md
Archived Sibling Plans: aiplans/archived/p2258/p2258_*_*.md
Base branch: main
Output branch: main
---

# t2258_4 — Workflows audit

## Context

Section audit of `website/content/docs/workflows/` (44 pages) against the level model in
`aitasks/metadata/doc_update_guide.md` (t2258_1), using `aitask-doc-review`
(t2258_2). Method: parent plan `aiplans/p2258_doc_audience_levels_and_readable_prose.md`
§ "Common audit method (children 3–7)". Read the archived pilot plan
`aiplans/archived/p2258/p2258_3_*.md` first for lessons and guide changes.

## Steps

1. **Inventory** every page of the section (lines, depth, type, verdict,
   violations) into a table in this plan.
2. **Shared-file gate** per page before editing (diff vs HEAD); dirty pages →
   skipped-page ledger (path, reason, dirty state seen).
3. **Restructure, longest first** (`bug-report-intake`, `freeze-and-restore-agents` — also the AI-tell sample — `manual-verification`, `shadow-agent`, `cross_project_dependencies`, `contribute-and-manage/contribution-flow`, `multi_project`, `crash-recovery`): keep each page a how-to (goal, steps, outcome); move internals to the owning reference/command/skill page or `aidocs/`; split pages that blend overview + steps + internals; update the hand-curated body list in `workflows/_index.md` for any new or split page. Record every moved fact. If the inventory shows more than one session of work, create further children of t2258 per workflow group at planning instead of shipping a partial audit.
4. **Review** each edited page with `aitask-doc-review` (fresh-reader on
   `main-concept` pages within the budget).
5. **Tag** every untagged leaf page with `depth:`.
6. **Links:** `cd website && python3 check_links.py --build`;
   `python3 check_link_relevance.py` for retargeted links, open every
   reported target.
7. **Feed lessons** into the guide's examples, not ad-hoc page fixes.
8. **Ledger close-out:** re-check skipped pages; audit now-clean ones; create
   `audit_deferred_pages_workflows` (child of t2258, `--no-sibling-dep`) for any
   still dirty. Record outcomes (`audited` / `follow-up t2258_<n>`) in Final
   Implementation Notes; do not archive with an entry lacking one.

## Verification

- Inventory, moved-fact table and ledger outcomes present in this plan.
- `check_links.py --build` exits 0.
- Every leaf page in the section has `depth:`.

## Post-implementation

Step 9 (review, commit `documentation: … (t2258_4)`, archival).
