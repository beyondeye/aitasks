---
Task: t194_documentation_for_explain_skill.md
Branch: main (current branch)
---

# Plan: Documentation for aitask-explain skill

## Context

The `/aitask-explain` skill exists but has no website documentation. The task requires two deliverables: a skill reference page and a workflow guide page. The workflow page should frame `/aitask-explain` as the tool for "cognitive debt" (understanding why code exists) complementing `/aitask-review` for "technical debt" (problems in code), referencing Margaret Storey's blog post on cognitive debt in AI-driven development.

## Files to Create/Modify

1. **Create** `website/content/docs/skills/aitask-explain.md` — Skill reference page (weight: 55)
2. **Update** `website/content/docs/skills/_index.md` — Add row to skill overview table
3. **Create** `website/content/docs/workflows/explain.md` — Workflow guide (weight: 85)

## Step 1: Create Skill Reference Page

**File:** `website/content/docs/skills/aitask-explain.md`

Structure (following patterns from aitask-review.md, aitask-explore.md):
- Frontmatter: title `/aitask-explain`, weight 55
- Opening paragraph: explains files across 3 dimensions, traces code back through aitask/aiplan history
- **Usage** section with 3 invocation forms (interactive, file path, directory)
- **Workflow Overview** — 6 numbered steps: File selection → Mode selection → Generate reference data → Analysis → Interactive follow-up → Cleanup
- **Key Capabilities** — 5 bullets: Three analysis modes, Line-to-task tracing, Run reuse, Directory expansion, Interactive drill-down
- **Run Management** — subsection on `aiexplains/` directory management with CLI examples
- Cross-reference to workflow guide

## Step 2: Update Skills Index

**File:** `website/content/docs/skills/_index.md`

Add new table row after `/aitask-explore`:
```
| [`/aitask-explain`](aitask-explain/) | Explain files: functionality, usage examples, and code evolution traced through aitasks |
```

## Step 3: Create Workflow Guide

**File:** `website/content/docs/workflows/explain.md`

Structure (following patterns from exploration-driven.md, code-review.md):
- Frontmatter: title "Understanding Code with Explain", weight 85
- **Opening paragraph** — Cognitive debt framing: AI agents ship faster than teams build understanding. Reference Storey blog post.
- **Bold philosophy line:** "Technical debt lives in the code; cognitive debt lives in developers' understanding."
- **Cognitive Debt vs Technical Debt** section — Frame `/aitask-review` for technical debt, `/aitask-explain` for cognitive debt. Cite blog post. Explain why aitasks is well-positioned (structured task/plan records capture the "why").
- **When to Use Explain** — 5 scenarios: AI-generated code understanding, onboarding, debugging with context, code review preparation, knowledge transfer
- **Walkthrough: Understanding a Refactored Module** — 6-step narrative with `aiscripts/lib/task_utils.sh` as example
- **How It Works** — Brief data pipeline diagram: target files → extract script → process script → reference.yaml → Claude explanation
- **Tips** — 5 tips: Start with code evolution, reuse runs, combine with review, explain directories, manage disk usage

## Verification

```bash
cd website && hugo build --gc --minify
```

Check: no build errors, new pages appear in sidebar, cross-references (relref) resolve correctly.

## Final Implementation Notes

- **Actual work done:** Created skill reference page (`website/content/docs/skills/aitask-explain.md`) with workflow overview, key capabilities, run management section, and cross-reference to workflow guide. Created workflow guide (`website/content/docs/workflows/explain.md`) with cognitive debt vs technical debt framing, Margaret Storey blog post reference, 5 use cases, walkthrough with `task_utils.sh` as example, data pipeline diagram, and tips. Updated skills index table with new entry.
- **Deviations from plan:** Initially used Hugo `relref` shortcodes for cross-references in the workflow page, but discovered all existing workflow pages use relative markdown links (`../../skills/aitask-review/`). Fixed to match existing convention.
- **Issues encountered:** Hugo build failed with 5 `REF_NOT_FOUND` errors from `relref` shortcodes. Resolved by switching to relative path links matching the convention in all other workflow pages.
- **Key decisions:** Weight 55 for skill page (between aitask-stats at 50 and aitask-changelog at 60). Weight 85 for workflow page (after releases at 80). Used relative links throughout the workflow page to match existing patterns.
