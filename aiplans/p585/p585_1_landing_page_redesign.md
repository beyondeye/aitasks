---
Task: t585_1_landing_page_redesign.md
Parent Task: aitasks/t585_better_frawework_desc_in_website.md
Sibling Tasks: aitasks/t585/t585_2_concepts_section.md, aitasks/t585/t585_3_overview_rewrite.md, aitasks/t585/t585_4_coherence_audit.md, aitasks/t585/t585_5_readme_revamp.md
Archived Sibling Plans: aiplans/archived/p585/p585_*_*.md
Worktree: aiwork/t585_1_landing_page_redesign
Branch: aitask/t585_1_landing_page_redesign
Base branch: main
---

# t585_1 — Landing Page Redesign

## Context

Redesign `website/content/_index.md` to reposition aitasks as **"A full agentic IDE in your terminal!"** with three hero feature cards on top and richer "deep-dive" sections below (user-approved "design option 3"). The current 3 low-level highlights (File-Based Tasks, Code Agent Integration, Parallel Development) no longer reflect the framework's scope.

Parent context: `aiplans/p585_better_frawework_desc_in_website.md`.

## Implementation Plan

### Step 1 — Cover/hero block

In `website/content/_index.md`, replace the current `blocks/cover` block:

- Tagline: replace `<p class="lead mt-2">AI-powered task management for code agents</p>` with `<p class="lead mt-2">A full agentic IDE in your terminal.</p>`.
- Optional subtagline below the lead: `<p>Kanban board, code browser, agent monitoring, and AI-enhanced workflows — all in tmux.</p>`.
- Keep the logo image and the "Documentation" CTA.
- Replace the GitHub button text with `⭐ Star on GitHub to support us!` (still pointing to `https://github.com/beyondeye/aitasks`). Use the unicode star directly.

### Step 2 — 3 hero highlights row

Replace the existing 3-feature `blocks/section type="row"` block. Use these (icon, title, body):

1. `fa-terminal` — **Agentic IDE in your terminal** — Kanban Board + Code Browser + Monitor + Brainstorm + Settings, all in one tmux session via `ait ide`. Press `j` to hop between TUIs without leaving the terminal.
2. `fa-brain` — **Long-term memory for agents** — Archived tasks and plans serve as queryable context. The Code Browser annotates each line back to the task and plan that introduced it.
3. `fa-code-branch` — **Tight git coupling, AI-enhanced** — PR import/close, issue tracker integration, contribution flow, changelog generation, and AI-assisted reverts — all rooted in git commits and task metadata.

Confirm these picks with the user briefly before committing if any feel weak in context.

### Step 3 — Deep-dive sections

Below the hero row, add three `blocks/section` blocks alternating `color="white"` / `color="light"`. Each section gets a heading, 1 short paragraph, and a 3-4 bullet list of concrete capabilities. Optional `blocks/lead` pull-quotes between sections for visual rhythm.

- **Task decomposition & parallelism** — auto-explode complex tasks into child tasks; sibling context propagation; git worktrees + atomic locks for parallel agent work. Link to `{{< relref "docs/workflows/task-decomposition" >}}` and `{{< relref "docs/workflows/parallel-development" >}}`.
- **AI-enhanced code review** — review guides per language, batched reviews, QA workflow, code explanations with task traceability. Link to `{{< relref "docs/workflows/code-review" >}}` and `{{< relref "docs/workflows/qa-testing" >}}`.
- **Multi-agent support with verified scores** — Claude Code, Gemini CLI, Codex CLI, OpenCode unified via the codeagent wrapper; per-model/per-operation scores accumulated from user feedback. Link to `{{< relref "docs/commands/codeagent" >}}` and `{{< relref "docs/skills/verified-scores" >}}`.

Cross-link to Concepts pages (`{{< relref "docs/concepts/ide-model" >}}`, `concepts/agent-memory`, `concepts/git-branching-model`, etc.) wherever natural — these may not yet be merged when this task lands; Hugo will warn but build.

### Step 4 — Platform-support strip

Add a `blocks/section type="row"` with 5 small `blocks/feature` items (icons: `fa-linux`, `fa-ubuntu`, `fa-fedora`, `fa-apple`, `fa-windows` — fall back to `fa-desktop` if a platform-specific icon is unavailable in the Docsy FontAwesome set). One-word body each. Link the section header to `{{< relref "docs/installation" >}}`.

### Step 5 — Trailing sections

Keep the existing `Latest Releases` (dark) and `Quick Install` (light) sections unchanged.

### Step 6 — Visual modernization (optional, minimal)

Only add custom CSS if a stock Docsy block looks visibly weak after the rewrite. Likely targets:

- Bigger hero h1 / increased line-height
- Accent color on hero CTA buttons

Locate the override file: check `website/assets/scss/_variables_project.scss` first, then `_styles_project.scss`. Add minimal overrides; do NOT introduce a new shortcode.

## Critical Files

- `website/content/_index.md` — full redesign
- `website/assets/scss/_variables_project.scss` (or `_styles_project.scss`) — only if a small visual override is needed
- Reference: `website/content/about/_index.md` — multi-section visual cadence pattern to mirror

## Existing Patterns to Reuse

- Docsy block shortcodes: `blocks/cover`, `blocks/section`, `blocks/feature`, `blocks/lead` — already used in `_index.md` and `about/_index.md`. No new shortcodes.
- `relref` for inter-page links — pattern at `website/content/docs/overview.md:43,49`.

## Verification

1. `cd website && ./serve.sh` — site builds, no Hugo errors.
2. Open `http://localhost:1313/` — visually verify hero, 3 hero cards, deep-dive sections, platform strip, "⭐ Star on GitHub to support us!" CTA.
3. Resize to mobile viewport (≤768px) — cards stack vertically, remain readable.
4. `Grep -n "Conductor\|Beads" website/content/_index.md` — zero matches.
5. Click each deep-dive link into existing pages (`workflows/`, `skills/`, `commands/`) — should resolve. `concepts/*` links may warn (sibling t585_2 hasn't merged yet); that is expected.

## Step 9 (Post-Implementation)

Standard task-workflow Step 9: review → commit code (`website/content/_index.md`, optional SCSS) using `git`, commit plan file using `./ait git`, archive with `./.aitask-scripts/aitask_archive.sh 585_1`, push.
