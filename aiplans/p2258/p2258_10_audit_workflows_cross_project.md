---
Task: t2258_10_audit_workflows_cross_project.md
Parent Task: aitasks/t2258_doc_audience_levels_and_readable_prose.md
Sibling Tasks: aitasks/t2258/t2258_*_*.md
Archived Sibling Plans: aiplans/archived/p2258/p2258_*_*.md
Base branch: main
Output branch: main
---

# t2258_10 — Workflows audit: Parallel group, cross-project and remote part

## Context

Split from t2258_4 at its planning (2026-11-12). This child audits the
Parallel group, cross-project and remote part of `website/content/docs/workflows/` (3 pages, about 615
lines) against the level model in `aitasks/metadata/doc_update_guide.md`, using
`aitask-docs-review`. Method: the task body's "Method (binding)", which follows
the parent plan's "Common audit method". Read the archived plans of t2258_3,
t2258_4 and every earlier workflows split child first.

## Steps

1. **Inventory** every page of the group (lines, depth, type, verdict,
   violations) into a table in this plan.
2. **Shared-file gate** before every edit, on source and destination pages;
   dirty pages go to the skipped-page ledger.
3. **Restructure, longest first.** Keep each page a how-to; move behaviour
   detail to the owning reference page, public architecture to `development/`
   and contributor-only detail to `aidocs/`. Check each fact against the code
   and record every move. Apply the task's Coordination items.
4. **Feed lessons** into the guide's examples (last planned guide change).
5. **Review** every edited or created page with
   `/aitask-docs-review … --caller audit` under the final guide.
6. **depth** on every leaf page of the group.
7. **Links:** `check_links.py --build`, `check_link_relevance.py` (open every
   reported target), `test_website_doc_lists.sh` when pages are added.
8. **Survival check** (claim-level, independent sub-agent) before the commit.
9. **Ledger close-out:** audit now-clean pages; create
   `audit_deferred_pages_workflows_cross_project` for any still dirty; record each
   outcome in Final Implementation Notes.

## Verification

- Inventory, moved-fact table, survival counts and ledger outcomes present in
  this plan.
- `check_links.py --build` exits 0.
- Every leaf page in the group has `depth:`.

## Post-implementation

Step 9 (review, commit `documentation: … (t2258_10)`, archival).
