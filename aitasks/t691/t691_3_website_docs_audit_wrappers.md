---
priority: medium
effort: low
depends: [t691_2]
issue_type: documentation
status: Implementing
labels: [claudeskills, documentation]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-04-28 11:07
updated_at: 2026-04-28 12:06
---

## Context

Adds a per-skill page on the project website for the new `aitask-audit-wrappers` skill (introduced by t691_1 + t691_2). Updates the existing `aitask-add-model.md` page to cross-reference it and updates `_index.md` to surface the new entry. Both pages are tagged as developer-facing (`maturity: experimental`, `depth: advanced`) so users browsing the site can tell they are framework-development tools.

Depends on t691_2 (Phase 2 must be implemented before docs can describe both phases accurately).

## Key files to modify

**New:**
- `website/content/docs/skills/aitask-audit-wrappers.md`

**Edit:**
- `website/content/docs/skills/aitask-add-model.md` — add cross-reference paragraph linking to the new audit-wrappers skill.
- `website/content/docs/skills/_index.md` — add row for `/aitask-audit-wrappers`.

## Reference files for patterns

- `website/content/docs/skills/aitask-add-model.md` — closest template (78 lines, `weight: 56`, `maturity: [experimental]`, `depth: [advanced]`).
- `website/content/docs/skills/aitask-refresh-code-models.md` — companion-skill cross-reference pattern.
- `website/content/docs/skills/_index.md` — table-row pattern under each grouping.

## Implementation plan

1. **New page** `website/content/docs/skills/aitask-audit-wrappers.md` modeled on `aitask-add-model.md`:
   - Hugo frontmatter:
     ```yaml
     ---
     title: "/aitask-audit-wrappers"
     linkTitle: "/aitask-audit-wrappers"
     weight: 57
     description: "Audit and port aitask skill wrappers across code-agent trees, plus helper-script whitelist coverage"
     maturity: [experimental]
     depth: [advanced]
     ---
     ```
   - Lead paragraph: what it does and why a multi-agent framework needs it.
   - **Usage** block with example invocations.
   - **When to Use** section comparing it to manual one-off ports (referencing how t689 was done by hand and this skill automates that).
   - **Phases** section explaining Phase 1 (wrappers) vs Phase 2 (helper whitelists) with confirmation-gate UX.
   - **Output** showing the structured `GAP:`/`POLICY_GAP:`/`MISSING:`/`WROTE:`/`COMMITTED:` lines.
   - **Self-bootstrap** note explaining first-introduction wrappers must be written by hand.
   - Cross-links: `aitask-add-model` (sibling dev-only skill), test files (verification), CLAUDE.md sections "WORKING ON SKILLS / CUSTOM COMMANDS" and "Adding a New Helper Script" as conceptual references.

2. **Update** `website/content/docs/skills/aitask-add-model.md`:
   - Add a paragraph (additive only, no content removal) noting that drift between `.claude/skills/` source-of-truth and the wrapper trees is now caught automatically by `/aitask-audit-wrappers`. Link to the new page.

3. **Update** `website/content/docs/skills/_index.md`:
   - Under "Configuration & Reporting", add a row:
     ```
     | [`/aitask-audit-wrappers`](aitask-audit-wrappers/) | Audit and port skill wrappers across all code-agent trees |
     ```

4. **Build verification.**
   ```bash
   cd website && hugo build --gc --minify
   ```

## Verification steps

1. `cd website && hugo build --gc --minify` — exits 0, no broken-link warnings touching the new or edited pages.
2. The new page renders at `/docs/skills/aitask-audit-wrappers/` (verify via the local `serve.sh`).
3. The `_index.md` row links resolve.
4. Cross-references to/from `aitask-add-model.md` resolve.

## Notes for sibling tasks

- If t697 (sibling top-level analysis of dev-only filtering) lands a recommendation that creates a "Framework Development" subsection in `_index.md`, that grouping change is t697's concern; this child slots audit-wrappers under existing "Configuration & Reporting" alongside `aitask-add-model`.
