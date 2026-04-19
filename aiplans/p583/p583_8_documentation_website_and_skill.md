---
Task: t583_8_documentation_website_and_skill.md
Parent Task: aitasks/t583_manual_verification_module_for_task_workflow.md
Sibling Tasks: aitasks/t583/t583_1_*.md .. t583_9_*.md
Archived Sibling Plans: aiplans/archived/p583/p583_*_*.md
Worktree: (current branch)
Branch: (current branch)
Base branch: main
---

# Plan: t583_8 — Documentation + CLAUDE.md Whitelisting Convention

## Context

User-facing documentation of the manual-verification module plus the CLAUDE.md whitelisting-convention note the user flagged as a recurring-issue guardrail.

Depends on all implementation children (t583_1..7) so docs describe shipping behavior.

## Files to create/modify

**New:**
- `website/content/docs/workflows/manual-verification.md`

**Modify:**
- `.claude/skills/aitask-pick/SKILL.md` (short Notes reference)
- `.claude/skills/aitask-explore/SKILL.md` (cross-reference)
- `CLAUDE.md` — two new subsections

## Website page structure

- Overview (two flows: generation, running).
- Checklist format (markdown checkbox states, ` — ` annotations).
- Generation flow (parent aggregate sibling vs single-task follow-up; explore path).
- Running flow (Pass/Fail/Skip/Defer semantics).
- Fail → follow-up bug (commits, files, failing-item capture; origin back-reference).
- `verifies:` field (what it is; how to set; drives origin disambiguation).
- Defer + carry-over.
- End-to-end example.

Front-matter per Docsy conventions: `title`, `weight`, `description`.

## CLAUDE.md edits

**Edit A — new "Manual verification" subsection under Project-Specific Notes:**
One-paragraph pointer to the website page and the procedure file.

**Edit B — new "Adding a New Helper Script" subsection** (parallel to existing "Adding a New Frontmatter Field" block):
Enumerate the 5 whitelist touchpoints (Claude runtime + Gemini runtime + Claude seed + Gemini seed + OpenCode seed) with entry shape examples. Note Codex exception (prompt-only permission model, no `allow` decision).

Per `feedback_doc_forward_only`: current state only; no "previously…" framing.

## Verification

- `cd website && hugo build --gc --minify` → new page builds without error.
- Browser render → headings/tables/code blocks correct.
- `grep -n "Manual verification" CLAUDE.md` → new subsection present.
- `grep -n "Adding a New Helper Script" CLAUDE.md` → new subsection present.

## Final Implementation Notes

_To be filled in during implementation._
