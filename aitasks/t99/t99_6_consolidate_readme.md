---
priority: medium
effort: medium
depends: [t99_1, t99_2, t99_3, t99_4, t99_5]
issue_type: documentation
status: Ready
labels: [aitasks]
created_at: 2026-02-12 10:56
updated_at: 2026-02-12 10:56
---

## Context
This is child task 6 of t99 (Update Scripts and Skills Docs). This is the consolidation task that depends on all 5 documentation snippet tasks (t99_1 through t99_5).

## Goal
Merge all documentation snippet files from `aitasks/t99/docs/` into README.md, producing the final updated documentation.

## Dependencies
This task depends on: t99_1, t99_2, t99_3, t99_4, t99_5. All snippet files must be complete before this task begins.

## Input Files
- `aitasks/t99/docs/01_crud_commands.md` — from t99_1 (ait create, ls, update + /aitask-create, /aitask-create2)
- `aitasks/t99/docs/02_utility_commands.md` — from t99_2 (ait board, stats, clear-old, setup + /aitask-stats, /aitask-cleanold)
- `aitasks/t99/docs/03_integration_commands.md` — from t99_3 (ait issue-import, issue-update, changelog + /aitask-changelog)
- `aitasks/t99/docs/04_pick_skill.md` — from t99_4 (/aitask-pick expanded docs)
- `aitasks/t99/docs/05_development.md` — from t99_5 (Architecture, Library Scripts)

## Steps

1. Read all 5 snippet files from `aitasks/t99/docs/`
2. Read current README.md
3. **Update Command Reference summary table** (lines 87-98):
   - Add row: `| ait changelog | Gather changelog data from commits and archived plans |`
4. **Update Claude Code Integration summary table** (lines 117-123):
   - Add row: `| /aitask-changelog | Generate changelog entries from commits and plans |`
5. **Insert command subsections** from snippets 01-03 after "### Usage Examples" section (after line 111):
   - Insert in order: ait create, ait ls, ait update, ait board, ait stats, ait clear-old, ait setup, ait issue-import, ait issue-update, ait changelog
6. **Update/add skill subsections** in Claude Code Integration section:
   - Replace existing `/aitask-pick` section with expanded version from snippet 04
   - Keep or update existing `/aitask-create` docs from snippet 01
   - Add new `/aitask-create2` section from snippet 01
   - Add new `/aitask-stats` section from snippet 02
   - Keep or update existing `/aitask-cleanold` docs from snippet 02
   - Add new `/aitask-changelog` section from snippet 03
7. **Insert Development subsections** from snippet 05 before "### Modifying scripts":
   - Add "### Architecture" and "### Library Scripts" subsections
8. **Fix typo:** "developement" → "development" on line 7
9. **Ensure consistent formatting:**
   - Heading hierarchy (## for sections, ### for subsections)
   - Table alignment
   - Code block formatting
   - No duplicate content between command docs and skill docs
10. **Clean up:** Remove `aitasks/t99/docs/` directory
11. **Commit:** Stage and commit README.md changes

## Reference Files
- `README.md` — The target file
- Plan file: `aiplans/p99_update_scripts_and_skills_docs.md` — Full plan with README structure

## Verification
- README renders correctly (check heading hierarchy, table formatting)
- All 10 commands have subsections under Command Reference
- All 6 skills are documented under Claude Code Integration
- Summary tables include `ait changelog` and `/aitask-changelog`
- "developement" typo is fixed
- No broken markdown (unclosed code blocks, malformed tables)
- Snippet files directory removed
