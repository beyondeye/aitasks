---
Task: t385_duplicated_procedures.md
Worktree: (current branch)
Branch: main
Base branch: main
---

## Context

Task t385 asks to check for duplicated procedures in `.claude/skills/task-workflow/procedures.md`. The file has grown organically as new procedures were added, and some content is repeated across related procedures.

## Duplications Found

### 1. "Final commit composition" in Code-Agent Commit Attribution duplicates Contributor Attribution

**Code-Agent Commit Attribution Procedure** (lines 236-270) has a "Final commit composition" section that restates the contributor attribution format already fully specified in **Contributor Attribution Procedure** (lines 129-208):

- Lines 238-256 re-describe the `Based on PR:` / `Co-Authored-By:` format rules verbatim
- Lines 258-270 show an example nearly identical to the one at lines 189-201 in the Multi-Contributor Attribution section

**Fix:** Replace the "Final commit composition" section with a brief cross-reference to the Contributor Attribution Procedure, keeping only the code-agent-specific rule (append agent trailer after any contributor trailers). Remove the duplicate example and keep just one combined example showing how all trailers compose together.

## Plan

### Step 1: Refactor Code-Agent Commit Attribution Procedure

In `procedures.md`, replace lines 236-270 (the "Final commit composition" section) with a concise cross-reference:

- Remove the duplicated contributor format rules
- Remove the duplicate example
- Add a short note: "Compose the final commit message following the format in the Contributor Attribution Procedure above, appending the code-agent trailer after any contributor trailers."
- Keep a single consolidated example showing all trailers together (already present in Multi-Contributor Attribution at line 192-201)

### Files to modify

- `.claude/skills/task-workflow/procedures.md` — the only file

### Verification

- Read the modified file and verify no information was lost
- Verify all cross-references are correct
- Check that SKILL.md references to procedures still make sense

### Step 9 (Post-Implementation)

Archive task, push changes.

## Final Implementation Notes
- **Actual work done:** Replaced the duplicated "Final commit composition" section (35 lines) in Code-Agent Commit Attribution Procedure with a single-line cross-reference to the Contributor Attribution Procedure and its Multi-Contributor Attribution example.
- **Deviations from plan:** None — implemented exactly as planned.
- **Issues encountered:** None.
- **Key decisions:** Kept the cross-reference pointing to the Multi-Contributor Attribution example (line 189-201) since it already includes both contributor and code-agent trailers, making it the most complete example.
