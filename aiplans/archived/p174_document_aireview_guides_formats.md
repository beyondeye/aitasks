---
Task: t174_document_aireview_guides_formats.md
Branch: main
Base branch: main
---

# Plan: Document aireviewguides Format and Algorithms (t174)

## Context

The aireviewguides system ships with the aitasks framework and is used by the `/aitask-review`, `/aitask-reviewguide-classify`, `/aitask-reviewguide-merge`, and `/aitask-reviewguide-import` skills. The guide file format, vocabulary files, environment detection algorithm, guide ranking, and similarity scoring are undocumented internals. The existing docs cover the user-facing workflow (`workflows/code-review.md`) and skill usage (`skills/aitask-review.md` etc.), but not the underlying data format and algorithms.

## Files to Modify

1. **Create** `website/content/docs/development/review-guide-format.md` — new reference page
2. **Edit** `website/content/docs/development/_index.md` — add `aireviewguides/` to Directory Layout table
3. **Edit** `docs/README.md` — add row to documentation index table

## Steps

### Step 1: Create `website/content/docs/development/review-guide-format.md`
- [x] New child page under Development (weight: 20)
- [x] File Structure section with frontmatter schema table
- [x] Directory Organization section
- [x] Vocabulary Files section
- [x] Environment Detection Algorithm section with scoring tables
- [x] Guide Ranking section
- [x] Similarity Scoring Algorithm section
- [x] See Also links

### Step 2: Edit `website/content/docs/development/_index.md`
- [x] Add `aireviewguides/` to Directory Layout table

### Step 3: Edit `docs/README.md`
- [x] Add row to documentation index table

## Verification
1. Check all internal links resolve
2. Verify page appears correctly in Development section

## Final Implementation Notes
- **Actual work done:** Created a comprehensive reference page documenting the review guide file format (frontmatter schema), directory organization, vocabulary files, environment detection algorithm (4 tests with scoring tables), guide ranking logic, and similarity scoring formula. Added `aireviewguides/` to the development directory layout table and the docs README index.
- **Deviations from plan:** Initially used Hugo `{{< relref >}}` shortcodes for cross-page links in the See Also section, but the project convention is regular relative markdown links. Fixed after Hugo build reported 5 REF_NOT_FOUND errors.
- **Issues encountered:** Hugo `relref` shortcodes don't resolve from `development/` to `workflows/` and `skills/` directories — switched to relative paths like `../workflows/code-review/` matching the pattern used in other doc files (e.g., `code-review.md`).
- **Key decisions:** Created a separate child page (`review-guide-format.md`, weight 20) rather than expanding `_index.md`, following the precedent of `task-format.md` (weight 10). This keeps focused reference documentation in dedicated sub-pages.
