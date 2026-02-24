---
Task: t233_update_license_to_apache2.md
Worktree: N/A (working on current branch)
Branch: main
Base branch: main
---

# Plan: Update License from MIT + Commons Clause to Apache 2.0 + Commons Clause (t233)

## Context

The project currently uses MIT License + Commons Clause. Switching the base license to Apache 2.0 while keeping the Commons Clause restriction provides:

- **Explicit Patent Grant** (Apache 2.0 Section 3): Contributors explicitly grant patent rights. MIT has no patent clause.
- **Trademark Protection** (Apache 2.0 Section 6): Explicitly does NOT grant permission to use trade names/trademarks.
- **Contribution Terms** (Apache 2.0 Section 5): Contributions are automatically under Apache 2.0 terms unless stated otherwise.
- **Commons Clause Compatibility**: The Commons Clause was designed to work with permissive licenses — Apache 2.0 was its primary example.

## Steps

- [x] 1. Update `LICENSE` file — replace MIT with Apache 2.0, keep Commons Clause
- [x] 2. Update `README.md` license section (lines 150-161)
- [x] 3. Update `website/content/about/_index.md` license section (lines 90-107)
- [x] 4. Verify consistency across all files — no remaining "MIT License" references in .md files

## Final Implementation Notes
- **Actual work done:** Replaced MIT License with full Apache License 2.0 text in LICENSE file, updated README.md and website about page to reference Apache 2.0 instead of MIT, added patent grant mention to user-facing permission summaries.
- **Deviations from plan:** None — straightforward text replacement across 3 files.
- **Issues encountered:** None.
- **Key decisions:** Kept the same dual-section structure (Commons Clause as Section 1, base license as Section 2). Added "explicit patent protection from contributors" to the website permissions table since that's the key user-facing differentiator from MIT.

## Post-Implementation (Step 9)
Archive task and plan per standard workflow.
