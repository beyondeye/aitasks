---
Task: t594_5_workflows_section_sweep.md
Parent Task: aitasks/t594_website_documentation_coherence.md
Parent Plan: aiplans/p594_website_documentation_coherence.md
Sibling Tasks: aitasks/t594/t594_{1,2,3,4,6}_*.md
Depends on: t594_2 (canonical wording)
Worktree: (none — work on current branch)
Branch: main
Base branch: main
---

# t594_5 — Workflows section coherence sweep

## Context

21 pages under `website/content/docs/workflows/`. Workflow pages often duplicate content with Skill pages (e.g., `workflows/qa-testing.md` ↔ `skills/aitask-qa.md`). Per conservative dedup stance, keep both — but add cross-links and canonicalize wording. Depends on t594_2 so canonical wording is already set.

## Scope

**In-bounds:**
- Add bidirectional cross-links between workflow ↔ skill page pairs.
- Canonicalize wording of repeated commands (especially `ait ide` launch sequence).
- Category intro for `workflows/_index.md` (Daily / Decomposition / Patterns / Integrations / Advanced) — no weight changes.
- "Next:" footers within the suggested reading path.
- Verify command sequences against actual shell scripts.

**Out-of-bounds:**
- Removing duplicate content from workflow pages (conservative stance).
- Reordering workflow pages by weight.
- Creating new workflow pages.

## Workflow↔Skill pairs to cross-link

| Workflow page | Skill page |
|---|---|
| `workflows/qa-testing.md` (if named this) | `skills/aitask-qa.md` |
| `workflows/code-review.md` | `skills/aitask-review.md` |
| `workflows/pr-import.md` | `skills/aitask-pr-import.md` |
| `workflows/contribution-flow.md` or `contribute-and-manage/*` | `skills/aitask-contribute.md` |
| `workflows/revert-changes.md` | `skills/aitask-revert.md` |
| `workflows/explain.md` | `skills/aitask-explain.md` |
| `workflows/task-decomposition.md` | `skills/aitask-explore.md`, `skills/aitask-fold.md` |
| `workflows/tmux-ide.md` | (no direct skill; primary daily workflow) |

Resolve exact filenames via `ls website/content/docs/workflows/`.

## Authoritative sources

| Claim | Source of truth |
|---|---|
| `ait ide` behavior | `.aitask-scripts/aitask_ide.sh` (resolve via `ls .aitask-scripts/`) |
| QA workflow steps | `.claude/skills/aitask-qa/SKILL.md` |
| Review workflow | `.claude/skills/aitask-review/SKILL.md` |
| PR-import | `.claude/skills/aitask-pr-import/SKILL.md` |
| Contribute flow | `.claude/skills/aitask-contribute/SKILL.md` |

## Implementation plan

1. **Inventory** workflow pages and map to corresponding skills via the table above.
2. **Cross-link pass** — for each pair, add "Related skill: /aitask-<name>" near the top of the workflow page, and "Related workflow: <workflow-page>" near the top of the skill page.
3. **Canonicalize `ait ide`** command and flags across `tmux-ide.md`, `parallel-development.md`, `capture-ideas.md`. Verify against `aitask_ide.sh`.
4. **Category intro for `workflows/_index.md`** — one paragraph introducing the five categories (Daily / Decomposition / Patterns / Integrations / Advanced), with a short one-sentence description of each. Do NOT change weights.
5. **"Next:" footer pass** within the reading path — suggested order follows weight ordering; confirm in each page's frontmatter.
6. **Source verification** — diff command sequences on each workflow page against the corresponding shell script / SKILL.md.
7. **Hugo build check.**

## Verification

- `grep -rn "ait ide" website/content/docs/workflows/` — all instances show the same canonical command.
- `grep -l "Related skill" website/content/docs/workflows/` returns the cross-linked pages.
- `workflows/_index.md` opens with the five-category intro paragraph.
- Open the top 5 workflow pages by weight (tmux-ide, capturing-ideas, retroactive-tracking, task-decomposition, task-consolidation) and the flow feels coherent.
- `cd website && hugo build --gc --minify` succeeds.

## Step 9 reference

Archive via `./.aitask-scripts/aitask_archive.sh 594_5`.
