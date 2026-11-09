---
Task: t2258_6_audit_skills_and_commands.md
Parent Task: aitasks/t2258_doc_audience_levels_and_readable_prose.md
Sibling Tasks: aitasks/t2258/t2258_1_*.md, aitasks/t2258/t2258_2_*.md, aitasks/t2258/t2258_3_*.md, aitasks/t2258/t2258_4_*.md, aitasks/t2258/t2258_5_*.md, aitasks/t2258/t2258_7_*.md, aitasks/t2258/t2258_8_*.md
Archived Sibling Plans: aiplans/archived/p2258/p2258_*_*.md
Base branch: main
Output branch: main
---

# t2258_6 — Skills and commands audit

## Context

Section audit of `website/content/docs/skills/` (41 pages) and `website/content/docs/commands/` (15 pages) against the level model in
`aitasks/metadata/doc_update_guide.md` (t2258_1), using `aitask-doc-review`
(t2258_2). Method: parent plan `aiplans/p2258_doc_audience_levels_and_readable_prose.md`
§ "Common audit method (children 3–7)". Read the archived pilot plan
`aiplans/archived/p2258/p2258_3_*.md` first for lessons and guide changes.

## Steps

1. **Inventory** every page of the section (lines, depth, type, verdict,
   violations) into a table in this plan.
2. **Shared-file gate** per page before editing (diff vs HEAD); dirty pages →
   skipped-page ledger (path, reason, dirty state seen).
3. **Restructure reference pages**: each opens with what the skill/command is for in plain words; remove narrative and embedded how-to steps (link to the workflow page instead); keep option/flag tables complete; keep literal agent enumerations only where the list is the documentation (`commands/codeagent.md`). Include `skills/aitask-doc-review.md` from t2258_2. Record every moved fact.
4. **Review** each edited page with `aitask-doc-review` (fresh-reader on
   `main-concept` pages within the budget).
5. **Tag** every untagged leaf page with `depth:`.
6. **Links:** `cd website && python3 check_links.py --build`;
   `python3 check_link_relevance.py` for retargeted links, open every
   reported target.
7. **Feed lessons** into the guide's examples, not ad-hoc page fixes.
8. **Ledger close-out:** re-check skipped pages; audit now-clean ones; create
   `audit_deferred_pages_skills_commands` (child of t2258, `--no-sibling-dep`) for any
   still dirty. Record outcomes (`audited` / `follow-up t2258_<n>`) in Final
   Implementation Notes; do not archive with an entry lacking one.

## Verification

- Inventory, moved-fact table and ledger outcomes present in this plan.
- `check_links.py --build` exits 0.
- Every leaf page in the section has `depth:`.

## Post-implementation

Step 9 (review, commit `documentation: … (t2258_6)`, archival).
