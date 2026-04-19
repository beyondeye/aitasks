---
Task: t585_2_concepts_section.md
Parent Task: aitasks/t585_better_frawework_desc_in_website.md
Sibling Tasks: aitasks/t585/t585_3_overview_rewrite.md, aitasks/t585/t585_4_coherence_audit.md, aitasks/t585/t585_5_readme_revamp.md
Archived Sibling Plans: aiplans/archived/p585/p585_1_landing_page_redesign.md
Base branch: main
plan_verified:
  - claudecode/opus4_7_1m @ 2026-04-19 12:45
---

# t585_2 — New "Concepts" Docs Section

## Context

The aitasks website lacks a top-level conceptual reference. Skill, workflow, and command pages document *how* to do things but don't explain *what* the framework's primitives are or *why* they exist. This task creates `website/content/docs/concepts/` (~12 pages + index) as the conceptual entry point — referenced from the redesigned landing page (t585_1, just merged) and the upcoming overview rewrite (t585_3).

Parent: `aiplans/p585_better_frawework_desc_in_website.md`. Sibling t585_1 already shipped the landing page redesign; t585_3 (overview) and t585_4 (coherence audit) depend on this section existing so they can cross-link into it.

## Verification Notes (2026-04-19)

Plan verified against current website state. Key findings from exploration:

- **Free section weight slot:** Existing weights are Installation 10, TUIs 30, Workflows 40, Skills 50, Commands 60, Development 70. Plan's `weight: 25` slot is free and fits between Getting Started/Overview and TUIs.
- **`relref` convention:** Use **absolute form** `{{< relref "/docs/concepts/<page>" >}}` (matches t585_1 + all existing docs) — NOT relative form. This refines the plan's original templates.
- **Top nav:** `hugo.toml` uses static `menu.main` config; sections opt in via frontmatter `menu.main.weight`. Plan's `menu: { main: { weight: 25 } }` for `_index.md` is correct.
- **Canonical link targets exist for 9/12 concepts**; 3 (`plans`, `agent-attribution`, `task-lifecycle`) become first canonical references. Their "How to use" sections summarize internally and link to source code via plain markdown links (e.g., `.claude/skills/task-workflow/agent-attribution.md` on GitHub) instead of `relref`.
- **No drift:** No conflicting recent changes; concepts/ does not yet exist.
- **Docsy gotcha (from t585_1):** brand icons in `blocks/feature` need `fab fa-...` prefix. Not relevant here (no `blocks/feature` use planned), but noted.

## Critical Files

- `website/content/docs/concepts/_index.md` (new)
- `website/content/docs/concepts/{tasks,plans,parent-child,folded-tasks,review-guides}.md` — data model (5 pages)
- `website/content/docs/concepts/{execution-profiles,verified-scores,agent-attribution,locks}.md` — workflow primitives (4 pages)
- `website/content/docs/concepts/{task-lifecycle,git-branching-model,ide-model,agent-memory}.md` — lifecycle + infrastructure (4 pages)
- Light-touch cross-link additions to 3-4 existing skill/workflow pages (Step 3)

## Implementation Plan

### Step 1 — Section index

`website/content/docs/concepts/_index.md`:

```yaml
---
title: "Concepts"
linkTitle: "Concepts"
weight: 25
description: "Conceptual reference for the aitasks framework — what each building block is and why it exists."
menu:
  main:
    weight: 25
---
```

Body (~30 lines): 1-paragraph intro framing Concepts vs. Workflows/Skills ("Concepts pages describe what the building blocks *are* and *why* they exist; for *how* to use them, see Workflows and Skills"), then a grouped bulleted index — Data Model / Workflow Primitives / Lifecycle + Infrastructure — with one-line description and `relref` link per page.

### Step 2 — 12 concept pages

For each page, frontmatter `weight` controls sidebar order: 10/20/30/40/50 within each group, with group offsets (data: 10-50, primitives: 60-90, lifecycle: 100-130).

Body template:

```markdown
## What it is
1 paragraph.

## Why it exists
1 paragraph (motivation, problem solved).

## How to use
Short — link to canonical page via `{{< relref "/docs/..." >}}`. For pages without an existing canonical doc (plans, agent-attribution, task-lifecycle), link to source files via plain markdown links to the GitHub repo.

## See also
- {{< relref "/docs/..." >}}
- {{< relref "/docs/..." >}}
```

**Source-of-truth + relref target map:**

| Page | Source of truth | "How to use" target |
|------|-----------------|---------------------|
| `tasks.md` | `CLAUDE.md` "Task File Format" section | `/docs/development/task-format` |
| `plans.md` | `.claude/skills/task-workflow/planning.md` (file naming + metadata header) | (no canonical — internal summary + GitHub link to `planning.md`) |
| `parent-child.md` | `CLAUDE.md` "Task Hierarchy" section | `/docs/workflows/task-decomposition` |
| `folded-tasks.md` | `CLAUDE.md` "Folded Task Semantics" — language MUST be "merged into" / "incorporated", never "superseded" / "replaced" | `/docs/skills/aitask-fold` |
| `review-guides.md` | `aireviewguides/` directory layout | `/docs/development/review-guide-format` |
| `execution-profiles.md` | `aitasks/metadata/profiles/*.yaml` + `.claude/skills/task-workflow/SKILL.md` "Execution Profiles" section | `/docs/skills/aitask-pick/execution-profiles` |
| `verified-scores.md` | `website/content/docs/skills/verified-scores.md` (link out, do not duplicate) | `/docs/skills/verified-scores` |
| `agent-attribution.md` | `.claude/skills/task-workflow/agent-attribution.md` + `model-self-detection.md` | (no canonical — internal summary + GitHub link) |
| `locks.md` | `.aitask-scripts/aitask_lock.sh` + `/docs/commands/lock` | `/docs/commands/lock` |
| `task-lifecycle.md` | Status transitions across `aitask_pick_own.sh`, `aitask_archive.sh`, abort procedure | (no canonical — internal summary + GitHub link to scripts) |
| `git-branching-model.md` | `.claude/skills/task-workflow/repo-structure.md` + `./ait git` wrapper | (no canonical website page; brief inline summary + GitHub link) |
| `ide-model.md` | `website/content/docs/workflows/tmux-ide.md` + `KNOWN_TUIS` in `.aitask-scripts/lib/tui_switcher.py` | `/docs/workflows/tmux-ide` |
| `agent-memory.md` | sibling-context propagation in `.aitask-scripts/aitask_query_files.sh` + Code Browser line annotation + `/aitask-explain` | `/docs/skills/aitask-explain` |

Each page ≤ 80 lines (excluding code/tables). Scannable, not tutorial.

### Step 3 — Cross-link existing docs into Concepts (light touch)

Append a "See also: [Concepts]({{< relref "/docs/concepts/<page>" >}})" line to:

- `website/content/docs/workflows/task-decomposition.md` → `concepts/parent-child`
- `website/content/docs/workflows/parallel-development.md` → `concepts/git-branching-model` (only if file exists; check first)
- `website/content/docs/workflows/tmux-ide.md` → `concepts/ide-model`
- `website/content/docs/skills/aitask-fold.md` → `concepts/folded-tasks`

Do NOT rewrite skill pages — single-line addition only.

### Step 4 — (Already covered in Step 1) Top-nav menu entry

The `menu.main.weight: 25` is set in `_index.md` frontmatter from Step 1.

## Style Rules

- Each page ≤ 80 lines (excluding code blocks/tables).
- Avoid duplicating reference content — link to canonical pages via `relref`.
- No "previously…" / "this used to be…" framing — describe current state only (CLAUDE.md doc rule).
- For `folded-tasks.md`: use "merged into" / "incorporated" — NEVER "superseded" / "replaced" (`feedback_folded_semantics`).
- Use absolute `relref` form: `{{< relref "/docs/concepts/<page>" >}}` (matches t585_1 + existing docs).

## Verification

1. `cd website && ./serve.sh` — site builds with no Hugo errors.
2. Open `http://localhost:1313/docs/concepts/` — `_index.md` renders with sub-page links and appears in top nav.
3. Navigate every page in the section sidebar — confirm hierarchy and internal links.
4. Click 3-5 `relref` links to skills/workflows pages — confirm they resolve.
5. `cd website && hugo --gc --minify` — strict build passes with no broken refs.

## Step 9 (Post-Implementation)

Standard task-workflow Step 9: review → commit doc files using `git`, commit plan file using `./ait git`, archive with `./.aitask-scripts/aitask_archive.sh 585_2`, push.

## Final Implementation Notes

- **Actual work done:** Created `website/content/docs/concepts/` with `_index.md` + 12 concept pages (tasks, plans, parent-child, folded-tasks, review-guides, execution-profiles, verified-scores, agent-attribution, locks, task-lifecycle, git-branching-model, ide-model, agent-memory). Each page follows the What/Why/How/See-also template, ≤80 lines. Added "See also: Concepts" cross-links to 4 existing pages (workflows/task-decomposition, workflows/parallel-development, workflows/tmux-ide, skills/aitask-fold). Total addition: 405 lines under `concepts/` plus 7 lines of cross-links elsewhere.
- **Deviations from plan:** (1) Dropped the planned `menu.main.weight: 25` from `_index.md` because `blog/_index.md` already uses `weight: 25` (collision). The convention used by sibling docs subsections (workflows, skills, commands, development, tuis) is to omit `menu.main` entirely and rely on the docs sidebar — Concepts now follows that convention. Plan's verification report incorrectly claimed those subsections had top-nav entries; verified directly that they do not. (2) After user review, applied 4 content fixes (see Post-Review Changes). The fixes affected only 4 of the 13 new files; the remaining 9 pages were accepted as written.
- **Issues encountered:** None at build time. The user review caught conceptual drift in the original draft — initial `tasks.md` recommended `/aitask-create` as the primary entry point, but the user clarified `ait create` (TUI-launched) is the recommended path with `/aitask-create` being one of many options. Reframed accordingly. Similarly, `git-branching-model.md` and `ide-model.md` initially over-emphasized terms ("branch mode", "fixed layout") that the user does not consider primary framing. The replacement framing in both is now driven by the actual implementation rather than legacy/historical wording.
- **Key decisions:**
  - Concept pages link to canonical docs via absolute `relref` (`/docs/...`), matching t585_1's convention.
  - Three concept pages without canonical website docs (`plans`, `agent-attribution`, `task-lifecycle`) link to GitHub source files via plain markdown links rather than fabricating relrefs to non-existent pages.
  - `folded-tasks.md` uses "merged into" / "incorporated" language exclusively, never "superseded" / "replaced", per the `feedback_folded_semantics` memory.
- **Notes for sibling tasks:**
  - **t585_3 (overview rewrite):** can now relref into `/docs/concepts/*` for definitional content. The 13 concept pages cover: tasks, plans, parent-child, folded-tasks, review-guides, execution-profiles, verified-scores, agent-attribution, locks, task-lifecycle, git-branching-model, ide-model, agent-memory. Whatever the rewritten overview cites conceptually, it can link there instead of redefining inline.
  - **t585_4 (coherence audit):** when scanning website for stale concepts/inconsistent terms, check that doc pages match the concept-page framing — particularly for "folded" (always "merged"/"incorporated", never "superseded"/"replaced") and "branching model" (treat the multi-branch layout as default, not as a special "branch mode").
  - **menu.main weight collision pattern:** before adding `menu.main.weight` to any new section index, run `grep -A2 "^menu:" website/content/**/_index.md` to verify the chosen weight is unused. The verification report I received earlier missed this and led to the deviation above. Better to subsection-default (no top-nav entry) unless top-level visibility is explicitly required.
  - **`relref` style:** use absolute form `{{< relref "/docs/<section>/<page>" >}}` consistently. This is established by t585_1 + t585_2 and is the only form that resolves cleanly from any nesting depth.
  - **Hugo build is fast and strict:** `cd website && hugo --gc --minify` finishes in ~700ms and errors on any broken `relref`. Use it as the verification gate after any docs change.

## Post-Review Changes

### Change Request 1 (2026-04-19 13:30)

- **Requested by user:** Tighten and correct four concept pages: (1) section index intro is too verbose/repetitive, (2) `tasks.md` "no separate database" framing is unclear and `/aitask-create` is wrongly recommended, (3) `git-branching-model.md` should not lead with "branch mode" (which is the default), (4) `ide-model.md` should not say "fixed layout" — the IDE is organized by tmux window-naming convention.
- **Changes made:**
  - `_index.md`: collapsed two-paragraph intro into one short sentence pointing at Workflows/Skills/Commands.
  - `tasks.md`: reframed persistence as "tasks persist exactly the same way source code does: as files committed to git"; rewrote "How to use" to point at `ait create` (TUI-launched), `/aitask-explore`, `/aitask-wrap`, `/aitask-pr-import`, and the Capturing-ideas + Create-tasks-from-code workflow pages — `/aitask-create` no longer surfaced.
  - `git-branching-model.md`: dropped "branch mode" / "legacy mode" framing; lead now states the multi-branch layout as the default; legacy fallback noted parenthetically at end.
  - `ide-model.md`: removed "fixed layout" wording; lead now describes the reserved tmux window names (`monitor`, `board`, `codebrowser`, `settings`, `brainstorm`, `agent-<n>`) and how the integrated TUIs look up windows by name. `ait ide` reframed as a bootstrapper, not the only entry point.
- **Files affected:** `website/content/docs/concepts/_index.md`, `website/content/docs/concepts/tasks.md`, `website/content/docs/concepts/git-branching-model.md`, `website/content/docs/concepts/ide-model.md`. Hugo strict build re-verified clean (148 pages, 0 errors).
