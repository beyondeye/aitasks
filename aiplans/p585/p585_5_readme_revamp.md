---
Task: t585_5_readme_revamp.md
Parent Task: aitasks/t585_better_frawework_desc_in_website.md
Sibling Tasks: aitasks/t585/t585_1_landing_page_redesign.md, aitasks/t585/t585_2_concepts_section.md, aitasks/t585/t585_3_overview_rewrite.md, aitasks/t585/t585_4_coherence_audit.md
Archived Sibling Plans: aiplans/archived/p585/p585_*_*.md
Worktree: aiwork/t585_5_readme_revamp
Branch: aitask/t585_5_readme_revamp
Base branch: main
---

# t585_5 — README.md Revamp

## Context

Update the project root `README.md` to mirror the new website positioning ("A full agentic IDE in your terminal"), restructure the feature highlights to match the website's 6 high-level themes, and remove all Conductor/Beads references.

Parent context: `aiplans/p585_better_frawework_desc_in_website.md`. Read archived sibling plans (`aiplans/archived/p585/p585_1_*.md`, `p585_3_*.md`) for the canonical positioning copy and the 6-theme structure to mirror.

## Implementation Plan

### Step 1 — Update tagline (line 8)

Current:

> *File-based task management for AI coding agents. No backend. Just markdown and git.*

Replace with the canonical landing-page tagline (verify exact wording from `aiplans/archived/p585/p585_1_*.md`):

> *A full agentic IDE in your terminal. File-based, git-native, multi-agent.*

### Step 2 — Update intro paragraph (lines 20-23)

Reframe around "agentic IDE in your terminal". Keep the supported-agents list (Claude Code, Gemini CLI, Codex CLI, OpenCode), but lead with the IDE positioning rather than "kanban-style workflow".

### Step 3 — Remove Conductor/Beads references

- Delete line 24 ("Inspired by [Conductor]…") entirely. Do not replace.
- Within "Key Features & Architecture" (Step 4 below), remove all parentheticals like "(Inspired by Conductor)" / "(The Beads Evolution)".

### Step 4 — Restructure "Key Features & Architecture" (lines 36-65)

Mirror the website's 6 themes. Each theme = 1-2 lines (README is much shorter than the website overview).

1. **Agentic IDE in your terminal** — TUIs (Board, Code Browser, Monitor, Brainstorm, Settings) in tmux, switchable with `j`.
2. **Long-term memory for agents** — archived tasks+plans queryable as context.
3. **Tight git coupling, AI-enhanced** — PR/issue/contribute/changelog/revert workflows.
4. **Task decomposition & parallelism** — child tasks, worktrees, atomic locking.
5. **AI-enhanced code review** — review guides, batched reviews, QA workflow.
6. **Multi-agent support with verified scores** — Claude Code, Gemini CLI, Codex CLI, OpenCode + per-model/per-operation scores.

Keep the existing dual-mode CLI bullet ("Interactive Mode for Humans" / "Batch Mode for Agents") if it still fits — it's framework-relevant, not positioning-conflicting. Trim if too verbose.

### Step 5 — Remove "Claude Code optimized." line (line 63)

Multi-agent support is now first-class. Fold into theme 6.

### Step 6 — Update GitHub references where applicable

Optional: rephrase any "GitHub" link text used as a CTA to "⭐ Star on GitHub to support us!". The badges at the top of the README should remain unchanged.

### Step 7 — Keep these sections unchanged

- Platform Support table (lines 67-75)
- Quick Install (lines 77-115)
- What Gets Installed (lines 115-130)
- Documentation links (lines 132-148)
- License (lines 150-160)

## Critical Files

- `README.md` (repo root) — restructured

## Existing Patterns to Reuse

- Section headers with emoji prefixes (🎯, 💡, 🏗️, 🖥️, ⚡, 📖, 📄) already used in current README — preserve this style.
- Markdown bullet structure (top-level + nested) — preserve.

## Style Rules

- README is shorter than website overview — keep theme bullets to 1-2 lines each.
- Cross-check theme order and terminology against the latest landing page (`website/content/_index.md`) — should be identical.
- Describe current state only — no "previously…" framing.

## Verification

1. `Grep "Conductor\|Beads" README.md` — zero matches.
2. Render the README via `glow README.md` (if available) or visit GitHub preview — confirm structure, links, and tone match the website.
3. Confirm all relative links and badges still resolve.
4. Cross-check theme order and terminology against the landing page (`website/content/_index.md`) — identical.

## Step 9 (Post-Implementation)

Standard task-workflow Step 9: review → commit `README.md` using `git`, commit plan file using `./ait git`, archive with `./.aitask-scripts/aitask_archive.sh 585_5`, push. The parent task t585 will auto-archive after this child completes (last child).
