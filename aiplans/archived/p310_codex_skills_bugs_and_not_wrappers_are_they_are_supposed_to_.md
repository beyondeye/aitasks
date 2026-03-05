---
Task: t310_codex_skills_bugs_and_not_wrappers_are_they_are_supposed_to_.md
Worktree: .
Branch: main
Base branch: main
---

## Implementation Plan
1. Reproduce and isolate which Codex skill file is invalid.
2. Validate frontmatter parsing across all `.agents/skills/*/SKILL.md` files.
3. Patch invalid frontmatter while keeping wrapper/source parity.
4. Re-validate all skill files in `.agents/skills/` and `.claude/skills/`.
5. Prepare task for archival in Step 9.

## Execution Notes
- Found one invalid skill frontmatter: `.agents/skills/aitask-explain/SKILL.md`.
- Root cause: unquoted `description` scalar included `:` which breaks YAML parsing.
- Applied same quoting fix in both Codex wrapper and Claude source skill to keep consistency.
- Validation after changes reports no invalid `SKILL.md` frontmatter in either tree.

## Final Implementation Notes
- **Actual work done:** Fixed invalid YAML frontmatter in `aitask-explain` skill definitions used by Codex wrappers and source skills.
- **Deviations from plan:** None; execution followed the planned diagnosis and patch flow.
- **Issues encountered:** No functional blockers; repository had unrelated dirty changes which were left untouched.
- **Key decisions:** Updated both `.agents` and `.claude` copies to prevent drift and future regeneration mismatch.
- **Build verification:** Not applicable for this content-only change; parser validation was performed with `yq`.
