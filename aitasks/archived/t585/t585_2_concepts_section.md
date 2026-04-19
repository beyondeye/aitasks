---
priority: medium
effort: high
depends: [t585_1]
issue_type: documentation
status: Done
labels: [web_site, positioning]
assigned_to: dario-e@beyond-eye.com
implemented_with: claudecode/opus4_7_1m
created_at: 2026-04-19 11:17
updated_at: 2026-04-19 13:47
completed_at: 2026-04-19 13:47
---

## Context

Create a new top-level **Concepts** section in the docs (`website/content/docs/concepts/`) — a full conceptual reference covering the framework's primitives. This is the user-approved "Full conceptual reference" scope (~12 pages: data model + workflow primitives + lifecycle + git branching + IDE model + memory).

This is child 2 of parent task t585. See parent plan `aiplans/p585_better_frawework_desc_in_website.md`. The Concepts section becomes the canonical conceptual entry point — referenced from the redesigned landing page (t585_1) and the rewritten overview (t585_3).

## Key Files to Modify

- `website/content/docs/concepts/_index.md` — section index
- `website/content/docs/concepts/<page>.md` — ~12 conceptual pages (list below)
- Possibly `website/hugo.toml` — only if menu weights need adjustment

## Reference Files for Patterns

- `website/content/docs/_index.md` — existing root section index pattern
- `website/content/docs/workflows/_index.md` — section _index with sub-page navigation
- `website/content/docs/tuis/_index.md` — section _index with sub-pages
- `website/content/docs/skills/_index.md` — section _index pattern
- `CLAUDE.md` (repo root) — authoritative source of truth for many concepts (folded semantics, frontmatter fields, branching model, etc.)
- `.claude/skills/task-workflow/SKILL.md` — context-variable table format we may want to mirror

## Implementation Plan

1. **Create `_index.md`** (frontmatter `weight: 25` to slot between Getting Started and TUIs):
   - Brief intro: "Conceptual reference for the aitasks framework. The pages here describe what the building blocks *are* and *why* they exist; for *how* to use them, see Workflows and Skills."
   - Inline navigation with one-line description per concept.

2. **Create the 12 concept pages** with consistent frontmatter (`weight: 10, 20, 30 ...` for ordering). Each page follows the same template:
   - **What it is** (1 paragraph)
   - **Why it exists** (1 paragraph)
   - **How to use** (short — link to canonical skill/workflow/command page via `relref`)
   - **See also** (3-5 cross-references)

   **Data model:**
   - `tasks.md` — Task file format: frontmatter fields (priority, effort, depends, issue_type, status, labels, etc.), filename pattern (`t<N>_<name>.md`), statuses overview (point to lifecycle page).
   - `plans.md` — Plan file format: location (`aiplans/p<N>_<name>.md`), metadata header, plan_verified entries, externalization for Claude Code.
   - `parent-child.md` — Parent task with child files in `aitasks/t<N>/`; auto-dependency between siblings; `children_to_implement` field; auto-archive of parent when all children complete.
   - `folded-tasks.md` — Folded tasks are **merged** into the primary (NOT "superseded" / "replaced" — see CLAUDE.md feedback). `folded_into` and `folded_tasks` fields; deletion at archival.
   - `review-guides.md` — Format and location (`aireviewguides/<lang>/`), classify/merge/import skills, link to code-review workflow.

   **Workflow primitives:**
   - `execution-profiles.md` — YAML schema in `aitasks/metadata/profiles/`, default profiles (default, fast, remote), per-skill defaults via `default_profiles` map. Brief schema table.
   - `verified-scores.md` — Per-model/per-operation 1-5 ratings, score buckets (0=untested, 1-49=partial, 50-79=verified, 80-100=highly verified). Time-windowed (all-time/month/week). Link to `skills/verified-scores/`.
   - `agent-attribution.md` — `implemented_with` field, agent string format `<agent>/<model>` (e.g., `claudecode/opus4_7_1m`), Co-Authored-By trailer. Link to model self-detection sub-procedure.
   - `locks.md` — Atomic task locking via `aitask-locks` branch; `aitask_lock.sh`; force-unlock semantics; lock surfacing in board TUI.

   **Lifecycle + infrastructure:**
   - `task-lifecycle.md` — States: Ready, Editing, Implementing, Postponed, Done, Folded. Transition diagram (text or simple list). Reference how skills move tasks between states.
   - `git-branching-model.md` — `aitask-data` (separate task data branch), `aitask-locks`, `aitask-ids` branches; `./ait git` wrapper; legacy mode pass-through; symlinks to `.aitask-data/`.
   - `ide-model.md` — `ait ide` boots a tmux session with the monitor TUI; `j` switcher hops between board/codebrowser/monitor/brainstorm/settings; agent windows; minimonitor sidebar.
   - `agent-memory.md` — Archived tasks+plans queryable as agent context; sibling-context propagation via `aitask_query_files.sh sibling-context`; Code Browser line annotation back to originating tasks; `/aitask-explain` evolution mode.

3. **Cross-link existing docs into the new Concepts pages** — light touch: optionally add a "See also: [Concepts]({{< relref "concepts/<page>" >}})" line to the most prominent skill/workflow pages that introduce a concept (e.g., `workflows/task-decomposition.md` → `concepts/parent-child.md`). Keep this minimal; don't rewrite skill pages.

4. **Optionally add to top-nav** — if `hugo.toml` (or section frontmatter) needs `menu.main.weight`, slot Concepts between Documentation (20) and Releases (25).

## Style Rules

- Each page should be **scannable** — short paragraphs, bulleted lists, tables for field/value reference.
- Avoid duplicating reference content — Concepts pages link to canonical skill/workflow/command pages via `relref`. They are the **conceptual entry point**, not a second source of truth.
- No "previously…" / "this used to be…" framing — describe current state only (per project doc rule, see CLAUDE.md).

## Verification Steps

1. `cd website && ./serve.sh` — site builds with no Hugo errors.
2. Open `http://localhost:1313/docs/concepts/` — `_index.md` renders with sub-page links.
3. Navigate every page in the section sidebar — confirm hierarchy and inter-doc cross-links work.
4. Click 3-5 `relref` links to skills/workflows pages — confirm they resolve.
5. Run a Hugo strict build: `hugo --gc --minify` from `website/` — should pass with no broken refs.

## Step 9 (Post-Implementation)

Follow standard task-workflow Step 9: review → commit doc files using `git`, commit plan file using `./ait git`, archive with `./.aitask-scripts/aitask_archive.sh 585_2`, push.
