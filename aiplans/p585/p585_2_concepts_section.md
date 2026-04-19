---
Task: t585_2_concepts_section.md
Parent Task: aitasks/t585_better_frawework_desc_in_website.md
Sibling Tasks: aitasks/t585/t585_1_landing_page_redesign.md, aitasks/t585/t585_3_overview_rewrite.md, aitasks/t585/t585_4_coherence_audit.md, aitasks/t585/t585_5_readme_revamp.md
Archived Sibling Plans: aiplans/archived/p585/p585_*_*.md
Worktree: aiwork/t585_2_concepts_section
Branch: aitask/t585_2_concepts_section
Base branch: main
---

# t585_2 — New "Concepts" Docs Section

## Context

Create a new top-level **Concepts** section under `website/content/docs/concepts/` covering the framework's conceptual primitives. Per user direction, scope is the **Full conceptual reference** (~12 pages: data model + workflow primitives + lifecycle + git branching + IDE model + memory). Concepts pages are the **conceptual entry point**, not a second source of truth — they link out to the canonical skill/workflow/command reference pages.

Parent context: `aiplans/p585_better_frawework_desc_in_website.md`.

## Implementation Plan

### Step 1 — Create section index

`website/content/docs/concepts/_index.md`:

```yaml
---
title: "Concepts"
linkTitle: "Concepts"
weight: 25
description: "Conceptual reference for the aitasks framework — what each building block is and why it exists."
---
```

Body: 1-paragraph intro framing Concepts vs. Workflows/Skills, then a bulleted index of every concept page with a one-line description and `relref` link.

### Step 2 — Create the 12 concept pages

For each page, use frontmatter `weight` to control sidebar order (e.g., 10, 20, 30…). Body template:

```markdown
## What it is
1 paragraph.

## Why it exists
1 paragraph (motivation, problem solved).

## How to use
Short — link to canonical skill/workflow/command page via relref.

## See also
- {{< relref "..." >}}
- {{< relref "..." >}}
```

**Data model:**

| File | Source of truth |
|------|-----------------|
| `tasks.md` | `CLAUDE.md` "Task File Format" section |
| `plans.md` | `.claude/skills/task-workflow/planning.md` (file naming + metadata header), externalization procedure |
| `parent-child.md` | `CLAUDE.md` "Task Hierarchy" section |
| `folded-tasks.md` | `CLAUDE.md` "Folded Task Semantics" — language MUST be "merged into" / "incorporated", never "superseded" / "replaced" |
| `review-guides.md` | `aireviewguides/` directory layout + `docs/development/review-guide-format.md` |

**Workflow primitives:**

| File | Source of truth |
|------|-----------------|
| `execution-profiles.md` | `aitasks/metadata/profiles/*.yaml` + `.claude/skills/task-workflow/SKILL.md` "Execution Profiles" section |
| `verified-scores.md` | `website/content/docs/skills/verified-scores.md` (link out, do not duplicate) |
| `agent-attribution.md` | `.claude/skills/task-workflow/agent-attribution.md` + `model-self-detection.md` |
| `locks.md` | `.aitask-scripts/aitask_lock.sh` + `.claude/skills/task-workflow/SKILL.md` Step 4 (lock outcomes) |

**Lifecycle + infrastructure:**

| File | Source of truth |
|------|-----------------|
| `task-lifecycle.md` | `aitasks/metadata/task_types.txt` + status transitions across `aitask_pick_own.sh`, `aitask_archive.sh`, abort procedure |
| `git-branching-model.md` | `ait git` wrapper + `.aitask-data/`, `aitask-locks`, `aitask-ids` branches; `.claude/skills/task-workflow/repo-structure.md` |
| `ide-model.md` | `website/content/docs/workflows/tmux-ide.md` + `KNOWN_TUIS` in `.aitask-scripts/lib/tui_switcher.py` |
| `agent-memory.md` | sibling-context propagation in `.aitask-scripts/aitask_query_files.sh` + Code Browser line annotation + `/aitask-explain` evolution mode |

### Step 3 — Cross-link existing docs into Concepts

Light touch only. Add a "See also: [Concepts]({{< relref "..." >}})" line to the most prominent skill/workflow pages that introduce a concept. Examples:

- `docs/workflows/task-decomposition.md` → `concepts/parent-child`
- `docs/workflows/parallel-development.md` → `concepts/git-branching-model`
- `docs/workflows/tmux-ide.md` → `concepts/ide-model`
- `docs/skills/aitask-fold.md` → `concepts/folded-tasks`

Do NOT rewrite skill pages — just add the cross-link.

### Step 4 — Optional: Top-nav menu entry

If the Concepts section should appear in the top nav, add `menu: { main: { weight: 25 } }` to `concepts/_index.md` frontmatter. Inspect `website/hugo.toml` first to confirm the nav uses the menu system rather than auto-generated entries.

## Critical Files

- `website/content/docs/concepts/_index.md` (new)
- `website/content/docs/concepts/<page>.md` — 12 new pages (see Step 2 table)
- `website/hugo.toml` — only if menu weights need adjustment

## Existing Patterns to Reuse

- Section `_index.md` with frontmatter weight: see `website/content/docs/workflows/_index.md`, `tuis/_index.md`.
- Per-page frontmatter with `weight`: see `website/content/docs/overview.md`.
- `relref` shortcode for inter-page links: see `docs/overview.md:43,49`.

## Style Rules

- Each page ≤ 80 lines (excluding code blocks/tables). Concepts pages are scannable, not tutorials.
- Avoid duplicating reference content — link to canonical pages via `relref`.
- No "previously…" / "this used to be…" framing — describe current state only.
- For `folded-tasks.md`: use "merged into" / "incorporated" — NEVER "superseded" / "replaced" (per `feedback_folded_semantics`).

## Verification

1. `cd website && ./serve.sh` — site builds with no Hugo errors.
2. Open `http://localhost:1313/docs/concepts/` — `_index.md` renders with sub-page links.
3. Navigate every page in the section sidebar — confirm hierarchy and internal links.
4. Click 3-5 `relref` links to skills/workflows pages — confirm they resolve.
5. `cd website && hugo --gc --minify` — strict build passes with no broken refs.

## Step 9 (Post-Implementation)

Standard task-workflow Step 9: review → commit doc files using `git`, commit plan file using `./ait git`, archive with `./.aitask-scripts/aitask_archive.sh 585_2`, push.
