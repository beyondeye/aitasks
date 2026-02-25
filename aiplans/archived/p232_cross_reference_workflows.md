---
Task: t232_cross_reference_workflows.md
Branch: main (current branch)
---

## Context

Skill doc pages in `website/content/docs/skills/` should cross-reference the workflow pages where the skill is central, similar to what `aitask-explain.md` and `aitask-fold.md` already do. Most skill pages currently lack this cross-reference.

## Current State

**Already have workflow cross-references (skip):**
- `aitask-explain.md` line 66 → `workflows/explain/`
- `aitask-fold.md` line 35 → `workflows/task-consolidation/`
- `aitask-web-merge.md` lines 71-76 → `workflows/claude-web/` (via "See Also" section)

**No dedicated workflow (skip):**
- `aitask-stats.md` — standalone utility, no workflow page

## Plan

Add a single-line workflow cross-reference at the end of each skill page that doesn't already have one. Follow the same pattern as aitask-explain:

```
For a full workflow guide, see [Workflow Name](../../workflows/slug/).
```

For skills with multiple relevant workflows, list them in a single sentence.

### Files to modify (11 files)

1. **`website/content/docs/skills/aitask-pick/_index.md`** → Task Decomposition + Parallel Development
2. **`website/content/docs/skills/aitask-pickrem.md`** → Parallel Development
3. **`website/content/docs/skills/aitask-pickweb.md`** → Claude Code Web
4. **`website/content/docs/skills/aitask-review.md`** → Code Review
5. **`website/content/docs/skills/aitask-explore.md`** → Exploration-Driven Development
6. **`website/content/docs/skills/aitask-create.md`** → Capturing Ideas + Follow-Up Tasks
7. **`website/content/docs/skills/aitask-wrap.md`** → Retroactive Change Tracking
8. **`website/content/docs/skills/aitask-changelog.md`** → Releases
9. **`website/content/docs/skills/aitask-reviewguide-classify.md`** → Code Review
10. **`website/content/docs/skills/aitask-reviewguide-import.md`** → Code Review
11. **`website/content/docs/skills/aitask-reviewguide-merge.md`** → Code Review

## Verification

1. Run `cd website && hugo build --gc --minify` to verify the site builds without errors
2. Spot-check rendered pages to verify links point to correct workflow pages

## Post-Review Changes

### Change Request 1 (2026-02-25)
- **Requested by user:** (1) Cross-reference links should be in their own `## Workflows` section at the end of each skill page, not inline in the previous section. (2) Rename `## Workflow Overview` / `## Workflow` headings in skill docs to `## Step-by-Step` to avoid confusion with "User Workflows" from docs/workflows/. (3) Replace "workflow" self-references in skill docs (e.g., "The workflow can...") with "skill".
- **Changes made:**
  - Moved all cross-references into dedicated `## Workflows` sections at the end of each skill page (11 new + 2 existing updated: aitask-explain, aitask-fold)
  - Renamed `## Workflow Overview` → `## Step-by-Step` in 13 skill pages
  - Renamed `## How It Works` → `## Step-by-Step` in aitask-web-merge
  - Replaced ~20 "workflow" self-references with "skill", "process", "lifecycle", or "flow" as contextually appropriate across 16 files
- **Files affected:** 16 files in `website/content/docs/skills/` (all skill doc pages including _index.md and build-verification.md)

## Final Implementation Notes
- **Actual work done:** Added `## Workflows` cross-reference sections to all skill doc pages that lacked them (11 new), updated 2 existing ones (aitask-explain, aitask-fold) to use the `## Workflows` heading. Renamed all `## Workflow Overview` and `## Workflow` headings in skill docs to `## Step-by-Step`. Replaced self-referencing uses of "workflow" with "skill" or equivalent.
- **Deviations from plan:** The original plan only covered adding cross-references. Per user feedback, scope expanded to include heading renames and terminology cleanup.
- **Issues encountered:** None — all edits were straightforward text replacements.
- **Key decisions:** Kept `## Suggested Workflow` in aitask-pickweb and aitask-web-merge unchanged since those describe user workflow diagrams (the local→web→local pattern), not skill steps. Used "process" for internal sub-processes (single-file process, single-pair process) and "flow" for general concepts (task flow).

### Change Request 2 (2026-02-25)
- **Requested by user:** (1) "a single skill" doesn't read well in pickrem/pickweb — use "flow" instead. (2) aitask-web-merge has double reference to Claude Web workflow (in Suggested Workflow section and See Also section).
- **Changes made:** Changed "a single skill" → "a single flow" in pickrem/pickweb. Removed duplicate Claude Web workflow link from aitask-web-merge See Also section.
- **Files affected:** aitask-pickrem.md, aitask-pickweb.md, aitask-web-merge.md
