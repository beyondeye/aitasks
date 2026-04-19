---
Task: t585_better_frawework_desc_in_website.md
Base branch: main
plan_verified: []
---

# t585 — Better Framework Description on Website (Parent Plan)

## Context

The website's landing page (`website/content/_index.md`) and the docs/overview pitch the framework with three low-level highlights — *File-Based Tasks, Code Agent Integration, Parallel Development* — that no longer reflect the framework's actual scope. Since those highlights were written, aitasks has grown into a tmux-integrated **agentic IDE** (Board, Code Browser, Monitor, Brainstorm), a long-term memory system (queryable archived tasks+plans linked to git), AI-enhanced git workflows (PR/issue/changelog/revert), AI-enhanced code review (review guides + QA), automatic decomposition + parallelism, multi-agent support with verified scores, and full Linux/macOS/WSL coverage.

The user wants:

1. A landing-page redesign with the positioning statement **"A full agentic IDE in your terminal!"**, three hero highlights, and richer "deep-dive" sections below — plus a more modern visual style.
2. A new top-level **Concepts** docs section that documents the framework's conceptual primitives (tasks, plans, lifecycle, git branching model, memory, etc.) with cross-references into the rest of the docs.
3. A rewrite of `docs/overview.md` and a coherence sweep of the rest of the docs so they line up with the new positioning.
4. Removal of all Conductor/Beads references from user-facing content (README, overview, about) — aitasks has diverged enough that these mentions are misleading.
5. A README revamp mirroring the new website positioning.
6. The "GitHub" CTA rephrased to **"⭐ Star on GitHub to support us!"** (or similar).

This is a multi-layer documentation task; per user direction it is split into **5 child tasks** under parent t585. Each child task gets its own implementation plan and can be picked independently with `/aitask-pick 585_<N>`.

---

## Top-3 Hero Features (recommended for the landing page)

1. **Agentic IDE in your terminal** — Kanban Board + Code Browser + Monitor + Brainstorm + Settings, all in one tmux session via `ait ide`, switchable with `j`.
2. **Long-term memory for agents** — Archived tasks and plans queryable as context; Code Browser annotates each line back to its originating task and plan.
3. **Tight git coupling, AI-enhanced** — PR import/close, issue tracker integration, contribution flow, changelog generation, and AI-assisted reverts — all rooted in git commits and task metadata.

The remaining three themes — **Task decomposition & parallelism**, **AI-enhanced code review (guides + QA)**, **Multi-agent support with verified scores** — become rich "deep-dive" sections below the hero row, alongside a platform-support strip (Arch, Ubuntu, Fedora, macOS, WSL).

The hero picks are recommendations; child task t585_1 is free to revise after a brief confirmation.

---

## Child Task Breakdown

### t585_1 — Landing page redesign (`website/content/_index.md`)

**Scope:**
- Replace the "AI-powered task management for code agents" tagline with **"A full agentic IDE in your terminal."**
- Replace the 3 existing feature cards with the 3 hero highlights above (icons: e.g. `fa-terminal`, `fa-brain`, `fa-code-branch`).
- Add a new "deep-dive" section below the hero row with subsections for: Task decomposition & parallelism, AI-enhanced code review, Multi-agent + verified scores. Use a mix of `blocks/section` with alternating `color="white"`/`light` for visual rhythm, plus `blocks/lead` pull-quotes between sections.
- Add a platform-support strip (5 platforms) using `blocks/feature` icons.
- Rephrase the secondary CTA from "GitHub" to **"⭐ Star on GitHub to support us!"**.
- Visual modernization: prefer Docsy's stock blocks (no new shortcodes) but lean on color variation, larger headings, and emoji/icon use to feel more modern. If a small CSS tweak is needed, add it to `website/assets/scss/_variables_project.scss` (or equivalent — to be confirmed during implementation).
- Verify links: every deep-dive subsection should link into the relevant page (Concepts, workflows, skills) — child task t585_2 may not yet be merged when this lands, so use `relref` to planned `concepts/<page>/` paths and accept temporary broken anchors (Hugo will warn but build).

**Verification:** `cd website && ./serve.sh`, open `http://localhost:1313/`, confirm hero, deep-dive sections, platform strip, and CTA all render. Check on mobile viewport.

---

### t585_2 — New "Concepts" docs section (`website/content/docs/concepts/`)

**Scope:** Create `_index.md` (weight: 25, menu.main.weight optional) and ~12 conceptual pages. Cross-reference into existing docs/skills/workflows.

**Pages to create** (one markdown file each, with consistent frontmatter `weight` for ordering):

Data model:
- `tasks.md` — Task file format (frontmatter fields, naming, statuses)
- `plans.md` — Plan file format, externalization, verification entries
- `parent-child.md` — Hierarchical task model and child auto-dependency
- `folded-tasks.md` — Merge semantics ("merged into", not "replaced")
- `review-guides.md` — Review guide format and import/classify/merge

Workflow primitives:
- `execution-profiles.md` — Profile YAML schema + when to use defaults
- `verified-scores.md` — Per-model/per-operation scoring (link to existing `skills/verified-scores.md` for full reference)
- `agent-attribution.md` — `implemented_with`, agent strings, co-author trailer
- `locks.md` — Atomic task locking on the `aitask-locks` branch

Lifecycle + infrastructure:
- `task-lifecycle.md` — States (Ready/Editing/Implementing/Postponed/Done/Folded) and transitions
- `git-branching-model.md` — `aitask-data`, `aitask-locks`, `aitask-ids` branches and worktree integration
- `ide-model.md` — The tmux + TUIs model (`ait ide`, `j` switcher, monitor as home screen)
- `agent-memory.md` — Archived tasks+plans as queryable agent context (Code Browser annotation, `/aitask-explain` traceability)

**Style rules:**
- Each page: 1-paragraph "What it is", 1-paragraph "Why it exists", short "How to use" / "See also" with `relref` to skills/workflows pages.
- Avoid duplicating reference content — link to canonical pages (skills/workflows). Concepts pages are the *conceptual* entry point, not a second source of truth.
- No "previously…" / "this used to be…" framing — describe current state only (per project doc rule).

**Verification:** `cd website && ./serve.sh`, open `http://localhost:1313/docs/concepts/`, navigate every page, confirm sidebar hierarchy and inter-doc cross-links work.

---

### t585_3 — Rewrite `docs/overview.md`

**Scope:**
- Reframe with the new positioning ("A full agentic IDE in your terminal").
- Remove all Conductor/Beads references (lines 24, 28).
- Replace the "Key Features & Architecture" bullet list with a structure aligned to the 6 high-level themes from the landing page; link each theme into the relevant `concepts/<page>/`.
- Add: codebrowser, monitor, brainstorm, verified scores (currently missing per exploration).
- Keep the "Challenge" + "Core Philosophy" framing but trim and modernize; consider removing the Speckit reference (line 17) too — confirm with user during implementation.

**Verification:** Build the site and check the page renders cleanly with no broken cross-references.

---

### t585_4 — Coherence audit + Conductor/Beads removal sweep

**Scope:**
- Update `website/content/about/_index.md`: remove the "Inspired by Conductor / Beads" sentence (line 21); rewrite the "How aitasks Started" section so it stands on its own (the Light-Spec philosophy story doesn't need the external scaffolding).
- Audit `docs/workflows/`, `docs/skills/`, `docs/commands/` for any inherited language that conflicts with the new positioning (e.g., docs that imply tasks are "just a kanban tool" vs. an IDE). Limit scope to landing-page-adjacent narrative pages — do **not** re-edit reference pages just to insert positioning copy.
- Run a final `Conductor|Beads|Speckit` grep across `website/content/` and confirm zero matches (Speckit confirmed for removal in this child task too if t585_3 chose to remove it).
- Update `docs/_index.md`'s one-line description if it conflicts with the new positioning.

**Verification:** `Grep -r "Conductor\|Beads"` in `website/content/` returns no results. Site builds cleanly.

---

### t585_5 — README.md revamp

**Scope:**
- Replace the tagline "File-based task management for AI coding agents…" with the new positioning.
- Remove the "Inspired by Conductor, and beads" line (line 24) and the two derived bullets (lines 37, 40, 42).
- Restructure "Key Features & Architecture" to mirror the website's 6 high-level themes (concise; the README is shorter than the website overview).
- Update GitHub CTA text where applicable.
- Keep the existing Platform Support table and Quick Install sections — they are accurate.
- Remove the "Claude Code optimized." line (line 63) — multi-agent support is now first-class; fold into the multi-agent theme.

**Verification:** Render README on GitHub (or `glow README.md`) and confirm structure, links, and tone.

---

## Critical Files

- `website/content/_index.md` — landing page (t585_1)
- `website/content/docs/overview.md` — overview (t585_3)
- `website/content/about/_index.md` — about (t585_4)
- `website/content/docs/_index.md` — root docs intro (t585_4 if needed)
- New tree: `website/content/docs/concepts/*.md` (t585_2)
- `README.md` — project root README (t585_5)
- `website/hugo.toml` — only if menu weights need adjustment for the new Concepts section (t585_2)
- `website/assets/scss/_variables_project.scss` (or similar) — only if a small style override is needed (t585_1)

## Existing patterns to reuse

- **Docsy block shortcodes** already used on the landing and about pages: `blocks/cover`, `blocks/section` (`color="white"|"dark"|"light"`, optional `type="row"`), `blocks/feature` (`icon=`, `title=`), `blocks/lead`. Stick to these — no new shortcodes required.
- **`relref` shortcode** for inter-page links — already used in `docs/overview.md:43,49` and elsewhere.
- **About page** (`about/_index.md`) already demonstrates a richer, multi-section layout (cover → narrative → lead → 3-feature row → narrative → table → 3-link row). The landing-page deep-dive should follow a similar visual cadence.

## Verification (overall)

After all 5 child tasks land:

1. `cd website && ./serve.sh` — site builds cleanly with no Hugo errors or broken cross-references.
2. Visit `http://localhost:1313/`, `/docs/`, `/docs/overview/`, `/docs/concepts/`, `/about/` — every page reflects the new positioning and has working internal links.
3. `Grep -r "Conductor\|Beads"` in `website/content/` and `README.md` → zero matches.
4. Render README on GitHub preview to confirm it lines up with the website tone.

## Step 9 (Post-Implementation) — reminder

Each child task follows the standard task-workflow Step 9 (review → commit code separately from plan → archive via `aitask_archive.sh` → push). The parent task t585 auto-archives after the last child completes.
