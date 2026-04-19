---
priority: medium
effort: medium
depends: []
issue_type: documentation
status: Implementing
labels: [web_site, positioning]
assigned_to: dario-e@beyond-eye.com
implemented_with: claudecode/opus4_7_1m
created_at: 2026-04-19 11:17
updated_at: 2026-04-19 11:52
---

## Context

Redesign the website landing page (`website/content/_index.md`) to reflect the framework's actual scope. Position aitasks as **"A full agentic IDE in your terminal!"** instead of the current low-level "AI-powered task management for code agents".

This is child 1 of parent task t585. See parent plan `aiplans/p585_better_frawework_desc_in_website.md` for the overall narrative and rationale.

The current landing page has 3 low-level feature cards (File-Based Tasks, Code Agent Integration, Parallel Development) that no longer reflect the agentic IDE scope. The new landing follows the user-approved "design option 3" — 3 hero features on top + detailed deep-dive sections below — with a more modern visual style.

## Key Files to Modify

- `website/content/_index.md` — full redesign
- `website/assets/scss/_variables_project.scss` — only if a small style override is needed (verify path during implementation; Docsy may use `_styles_project.scss`). Do NOT add custom shortcodes.

## Reference Files for Patterns

- `website/content/about/_index.md` — multi-section richer layout pattern (cover → narrative → lead → 3-feature row → narrative → table → 3-link row). Mirror the visual cadence.
- `website/content/_index.md` (current) — existing block usage to preserve
- Docsy block shortcodes in use: `blocks/cover`, `blocks/section` (`color="white"|"dark"|"light"`, optional `type="row"`), `blocks/feature` (`icon=`, `title=`), `blocks/lead`

## Implementation Plan

1. **New cover/hero block:**
   - Replace tagline `<p class="lead mt-2">AI-powered task management for code agents</p>` with **"A full agentic IDE in your terminal."**
   - Optionally add a one-line subtagline below: e.g., "Kanban board, code browser, agent monitoring, and AI-enhanced workflows — all in tmux."
   - Keep the logo image and the two CTA buttons. Rephrase the GitHub button to **"⭐ Star on GitHub to support us!"**.

2. **3 hero highlights (`blocks/section type="row"`):**
   - **Agentic IDE in your terminal** (icon: `fa-terminal`) — Kanban Board + Code Browser + Monitor + Brainstorm + Settings, all in one tmux session via `ait ide`, switchable with `j`.
   - **Long-term memory for agents** (icon: `fa-brain`) — Archived tasks and plans queryable as context; Code Browser annotates each line back to its originating task and plan.
   - **Tight git coupling, AI-enhanced** (icon: `fa-code-branch`) — PR import/close, issue tracker integration, contribution flow, changelog generation, and AI-assisted reverts — all rooted in git commits and task metadata.
   - The hero picks above are recommendations; you may revise after a brief user confirmation.

3. **Deep-dive sections (alternating `color="white"`/`light` for visual rhythm):**
   - **Task decomposition & parallelism** — explosion of complex tasks into child tasks with sibling context propagation; git worktrees + atomic locking for parallel agent work. Link to `workflows/task-decomposition/` and `workflows/parallel-development/`.
   - Optional `blocks/lead` pull-quote between sections.
   - **AI-enhanced code review** — review guides, batched reviews, QA workflow, code explanations. Link to `workflows/code-review/` and `workflows/qa-testing/`.
   - **Multi-agent support with verified scores** — Claude Code, Gemini CLI, Codex CLI, OpenCode unified via codeagent wrapper; per-model/per-operation scores from user feedback. Link to `commands/codeagent/` and `skills/verified-scores/`.

4. **Platform-support strip (`blocks/section type="row"` with 5 small `blocks/feature` icons):**
   - Arch, Ubuntu, Fedora, macOS, WSL — each with a tiny icon and one-word note. Link to `installation/`.

5. **Keep existing trailing sections:** Latest Releases (dark) and Quick Install (light) — unchanged unless they conflict with the new positioning.

6. **Cross-references to Concepts pages:** Use `relref` to planned `concepts/<page>/` paths (these will be created by sibling t585_2). Hugo will warn but build; this is acceptable for a transient state.

7. **Visual modernization:**
   - Prefer Docsy's stock blocks (no new shortcodes).
   - Use color variation (`white`/`light`/`dark`) and emoji/icons in headings to feel more modern.
   - If a small CSS tweak is needed (e.g., bigger hero headings, accent color), add to `website/assets/scss/_variables_project.scss` (verify exact path during implementation). Keep CSS changes minimal.

## Verification Steps

1. `cd website && ./serve.sh` — site builds with no Hugo errors.
2. Open `http://localhost:1313/` and visually verify:
   - New positioning statement renders in the hero
   - Three hero feature cards render in a row
   - Deep-dive sections render with alternating background colors
   - Platform-support strip renders
   - "⭐ Star on GitHub to support us!" CTA renders correctly (no broken HTML entity)
3. Resize to mobile viewport (≤768px) — confirm cards stack vertically and remain readable.
4. Run `Grep -r "Conductor\|Beads"` against `website/content/_index.md` — should return zero matches.
5. Click each deep-dive link — Hugo may warn about missing `concepts/*` refs (created by t585_2); links into existing `workflows/`/`skills/`/`commands/` pages must work.

## Step 9 (Post-Implementation)

Follow standard task-workflow Step 9: review → commit code (`website/content/_index.md`, optional SCSS) using `git`, commit plan file using `./ait git`, archive with `./.aitask-scripts/aitask_archive.sh 585_1`, push.
