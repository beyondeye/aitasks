---
Task: t2258_7_audit_entry_pages_and_depth_check.md
Parent Task: aitasks/t2258_doc_audience_levels_and_readable_prose.md
Sibling Tasks: aitasks/t2258/t2258_1_*.md, aitasks/t2258/t2258_2_*.md, aitasks/t2258/t2258_3_*.md, aitasks/t2258/t2258_4_*.md, aitasks/t2258/t2258_5_*.md, aitasks/t2258/t2258_6_*.md, aitasks/t2258/t2258_8_*.md
Archived Sibling Plans: aiplans/archived/p2258/p2258_*_*.md
Base branch: main
Output branch: main
---

# t2258_7 — Entry pages audit and depth-required check

## Context

Section audit of the entry pages: `overview.md`, `getting-started.md`, `installation/`, `development/` and every section `_index.md` against the level model in
`aitasks/metadata/doc_update_guide.md` (t2258_1), using `aitask-doc-review`
(t2258_2). Method: parent plan `aiplans/p2258_doc_audience_levels_and_readable_prose.md`
§ "Common audit method (children 3–7)". Read the archived pilot plan
`aiplans/archived/p2258/p2258_3_*.md` first for lessons and guide changes.

## Steps

1. **Inventory** every page of the section (lines, depth, type, verdict,
   violations) into a table in this plan.
2. **Shared-file gate** per page before editing (diff vs HEAD); dirty pages →
   skipped-page ledger (path, reason, dirty state seen).
3. **Restructure**: `overview.md` as a main-concept explanation, `getting-started.md` as a tutorial (one path, every term defined), installation pages as how-tos, section indexes as plain overviews. Then **add the depth-required check**: a small script under `website/` (or a flag on an existing checker) that fails when a leaf page under `website/content/docs/` (not `_index.md`) lacks `depth:`; wire it into `.github/workflows/hugo.yml` beside `check_links.py`; document it in `website/README.md` and CLAUDE.md's Website section; negative control — a scratch page without `depth:` makes it fail, then remove it. Run the check over the whole tree after tagging the remaining untagged pages (`installation/{pypy,linux,updating-model-lists}.md`, `development/pypy.md`, `tuis/applink/*` if t2258_5 left them). Record every moved fact.
4. **Review** each edited page with `aitask-doc-review` (fresh-reader on
   `main-concept` pages within the budget).
5. **Tag** every untagged leaf page with `depth:`.
6. **Links:** `cd website && python3 check_links.py --build`;
   `python3 check_link_relevance.py` for retargeted links, open every
   reported target.
7. **Feed lessons** into the guide's examples, not ad-hoc page fixes.
8. **Ledger close-out:** re-check skipped pages; audit now-clean ones; create
   `audit_deferred_pages_entry_pages` (child of t2258, `--no-sibling-dep`) for any
   still dirty. Record outcomes (`audited` / `follow-up t2258_<n>`) in Final
   Implementation Notes; do not archive with an entry lacking one.

## Verification

- Inventory, moved-fact table and ledger outcomes present in this plan.
- `check_links.py --build` exits 0.
- Every leaf page in the section has `depth:`.

## Post-implementation

Step 9 (review, commit `documentation: … (t2258_7)`, archival).
