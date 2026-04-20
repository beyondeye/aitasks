---
Task: t594_5_workflows_section_sweep.md
Parent Task: aitasks/t594_website_documentation_coherence.md
Parent Plan: aiplans/p594_website_documentation_coherence.md
Sibling Tasks: aitasks/t594/t594_{1,2,3,4,6}_*.md
Depends on: t594_2 (canonical wording)
Worktree: (none — work on current branch)
Branch: main
Base branch: main
plan_verified:
  - claudecode/opus4_7_1m @ 2026-04-20 12:42
---

# t594_5 — Workflows section coherence sweep (verified)

## Context

Child of t594. Sweep the 21 pages under `website/content/docs/workflows/` for cross-link gaps, category structure, command alignment with source, and reading-path coherence. Verification against current code/docs (2026-04-20) narrowed the original scope: most cross-link work is already done, and `ait ide` appears in only one page — not three.

## Verified state (as of 2026-04-20)

**Inventory:** 19 files directly under `workflows/` (including `_index.md`) + 2 files under `workflows/contribute-and-manage/` = 21 markdown pages. Weight-sorted ascending: `tmux-ide (5) → capturing-ideas (10) → retroactive-tracking (15) → task-decomposition (20) → task-consolidation (25) → issue-tracker (30) → pr-workflow (35) → parallel-development (40) → parallel-planning (45) → claude-web (50) → follow-up-tasks (60) → create-tasks-from-code (65) → code-review (70) → qa-testing (75) / exploration-driven (75) → releases (80) → explain (85) → revert-changes (90)`. `_index.md` weight is 40.

**Cross-link state (already bidirectional for 6/7 pairs):** qa-testing, code-review, pr-workflow, contribute-and-manage/contribution-flow, revert-changes, explain all have inline cross-links in both directions (workflow pages reference `/aitask-<name>`; skill pages reference `../../workflows/<page>/`). **Only gap:** `task-decomposition.md` has no cross-link to `aitask-explore` or `aitask-fold`.

**`ait ide` mentions:** only `tmux-ide.md` invokes the command. `parallel-development.md` and `capturing-ideas.md` do **not** mention it. The authoritative script `.aitask-scripts/aitask_ide.sh` exposes `ait ide [--session NAME]`, requires tmux, and reads `tmux.default_session` from `project_config.yaml` (falling back to `"aitasks"`). Current `tmux-ide.md` shows only bare `ait ide` with no prerequisite or flag.

**`_index.md`:** flat 2-line intro + single `**Next:**` footer to skills. No category grouping exists.

**"Next:" footer state:** one footer on `_index.md`; two `See also:` patterns on `parallel-development.md` and `task-decomposition.md`. No reading-path chain exists.

## Scope

**In-bounds:**
- Add missing `task-decomposition.md → aitask-explore / aitask-fold` cross-link (inline prose style, matching existing convention).
- Rewrite `workflows/_index.md` to introduce five categories (Daily / Decomposition / Patterns / Integrations / Advanced) and list the pages under each. No weight changes.
- Update `tmux-ide.md`'s `ait ide` description to match `aitask_ide.sh` behavior (document `--session NAME`, mention tmux prerequisite).
- Add a "Next:" footer chain across the five lowest-weight pages: `tmux-ide → capturing-ideas → retroactive-tracking → task-decomposition → task-consolidation`.
- Spot-check existing workflow-page `/aitask-<name>` cross-links resolve (no 404s on Hugo build).
- Run Hugo build as the final verification.

**Out-of-bounds** (confirmed with user, 2026-04-20):
- Standardizing cross-links to a uniform "Related skill:" top-of-page header — existing inline prose is acceptable.
- Adding `ait ide` pointers to `parallel-development.md` / `capturing-ideas.md` — those pages have different scopes.
- Removing duplicate content between workflow and skill pages (conservative dedup stance).
- Reordering pages by weight.
- Creating new workflow pages.

## Authoritative sources

| Claim | Source of truth |
|---|---|
| `ait ide` behavior, flags, prerequisites | `.aitask-scripts/aitask_ide.sh` |
| QA workflow steps | `.claude/skills/aitask-qa/SKILL.md` |
| Task decomposition via skills | `.claude/skills/aitask-explore/SKILL.md`, `.claude/skills/aitask-fold/SKILL.md` |

## Implementation steps

### 1. `task-decomposition.md` cross-link gap fix

- Read `website/content/docs/workflows/task-decomposition.md`.
- Add an inline cross-link near the top (within the first 1-2 content paragraphs, before any headings) pointing to the two skills that automate decomposition, matching the existing prose convention used by other pages:
  > For skill-driven decomposition, see [`/aitask-explore`](../../skills/aitask-explore/) (explore-first flow) and [`/aitask-fold`](../../skills/aitask-fold/) (merge related tasks).
- Keep the existing manual-decomposition narrative — this page covers the conceptual pattern; the skills pages cover the tools.

### 2. `_index.md` category grouping

- Rewrite `website/content/docs/workflows/_index.md` to introduce the five categories as manual markdown subsections (no Hugo taxonomy changes — that is t594_7's scope). Preserve the existing `description` frontmatter. Keep it scannable — one short paragraph per category plus a bulleted page list.
- Category assignment (no weight changes; pages remain sortable by weight in any auto-generated list):
  - **Daily** — tmux-ide, capturing-ideas, retroactive-tracking, follow-up-tasks, create-tasks-from-code
  - **Decomposition** — task-decomposition, task-consolidation, exploration-driven
  - **Patterns** — parallel-development, parallel-planning, claude-web, code-review
  - **Integrations** — issue-tracker, pr-workflow, contribute-and-manage/
  - **Advanced** — qa-testing, releases, explain, revert-changes
- Keep the existing `**Next:**` footer (pointing to skills) at the bottom.
- **Note for t594_7:** add a short HTML comment at the top of the category block (non-rendering) flagging the assignment as candidate source data for a future Hugo taxonomy. Example:
  ```html
  <!-- t594_7 note: these five groupings are candidate source data for a `workflow_category` Hugo taxonomy. When t594_7 lands, this manual grouping can be replaced by taxonomy-driven rendering. -->
  ```
  This is a deliberate pointer from the doc to the follow-up task; it costs nothing at render time and keeps the planning trail discoverable.

### 3. `tmux-ide.md` — `ait ide` alignment

- Read `website/content/docs/workflows/tmux-ide.md`.
- Replace the bare `ait ide` invocation in the "Open a terminal, go to your project, and run:" block with a two-line snippet showing both the default and the `--session NAME` variant.
- Add one short sentence immediately below the snippet:
  > Requires tmux (3.x or newer) to be installed. `ait ide` starts (or attaches to) the session named by `tmux.default_session` in `aitasks/metadata/project_config.yaml` (falling back to `aitasks`). The session gets a single `monitor` window running `ait monitor`; other TUIs are launched from within monitor via the TUI switcher.
- Leave the rest of the page's flow (picking a task, monitor dashboard, etc.) intact.

### 4. "Next:" footer chain — five lowest-weight pages

For each of the five pages below, append (or replace, if a shorter-form footer already exists) a uniform footer block at the very bottom of the file:

```markdown
---

**Next:** [<linkTitle>](../<slug>/) — <one-sentence blurb from that page's description>
```

Chain:
1. `tmux-ide.md` → `capturing-ideas.md`
2. `capturing-ideas.md` → `retroactive-tracking.md`
3. `retroactive-tracking.md` → `task-decomposition.md`
4. `task-decomposition.md` → `task-consolidation.md`
5. `task-consolidation.md` → leave as chain terminus (optionally link back to the workflows index)

Blurbs come verbatim from each page's `description:` frontmatter (already written — no new wording needed). Preserve existing `See also:` lines (`parallel-development.md`, `task-decomposition.md`) — they cover lateral links, not the sequential reading path.

### 5. Source-alignment spot check

After the edits above, run:

```bash
grep -rn "ait ide" website/content/docs/workflows/
grep -rn "/aitask-" website/content/docs/workflows/ | wc -l
```

Confirm the only `ait ide` mentions are in `tmux-ide.md` and that the total `/aitask-<name>` link count did not decrease. For each `/aitask-<name>` path referenced in the workflows pages, confirm the target skill page exists under `website/content/docs/skills/`.

### 6. Hugo build verification

```bash
cd website && hugo build --gc --minify
```

Must succeed with zero errors. Warnings about unrelated broken links are acceptable only if they pre-exist this task; otherwise fix them.

## Key files to modify

- `website/content/docs/workflows/_index.md` — rewrite with five-category intro.
- `website/content/docs/workflows/tmux-ide.md` — align `ait ide` usage with script; add Next footer.
- `website/content/docs/workflows/capturing-ideas.md` — add Next footer.
- `website/content/docs/workflows/retroactive-tracking.md` — add Next footer.
- `website/content/docs/workflows/task-decomposition.md` — add cross-link to aitask-explore/aitask-fold; add Next footer.
- `website/content/docs/workflows/task-consolidation.md` — add Next footer (terminus).

## Verification

- `grep -rn "ait ide" website/content/docs/workflows/` — all mentions are in `tmux-ide.md` only, and all show the same canonical invocation style (default + `--session NAME`).
- `grep -n "aitask-explore\|aitask-fold" website/content/docs/workflows/task-decomposition.md` — returns at least one match.
- `website/content/docs/workflows/_index.md` opens with the five-category intro; each category lists its pages.
- Open the chain pages in order (`tmux-ide` → `capturing-ideas` → `retroactive-tracking` → `task-decomposition` → `task-consolidation`); each page ends with a "Next:" footer pointing to the next in the chain (except the terminus).
- `cd website && hugo build --gc --minify` succeeds.

## Step 9 reference

Archive via `./.aitask-scripts/aitask_archive.sh 594_5`.

## Post-Review Changes

### Change Request 1 (2026-04-20 12:15)

- **Requested by user:** Restructure the `_index.md` category grouping and delete `tmux-ide.md` entirely.
  - Delete `website/content/docs/workflows/tmux-ide.md` and integrate its essential content into the existing `ait ide` documentation (`installation/terminal-setup.md`, `concepts/ide-model.md`, `getting-started.md`). The `--session` flag and session-sharing gotcha are already covered in `terminal-setup.md`, so "integrate" reduces to updating cross-references to point at those existing homes rather than at the deleted workflow page.
  - Merge **Daily** and **Decomposition** into a single **Tasks** category.
  - Rename **Integrations** to **Git**; move `releases` and `revert-changes` from **Advanced** into **Git**.
  - Add a new **Parallel** category covering `parallel-development`, `parallel-planning`, `claude-web`.
  - Add a new **Review & Quality** category covering `code-review`, `qa-testing`, `explain`.
  - The **Advanced** category disappears (its three pages redistributed).
- **Changes made:**
  - `website/content/docs/workflows/tmux-ide.md` deleted.
  - `website/content/docs/workflows/_index.md` rewritten with four categories: **Tasks / Parallel / Review & Quality / Git**. Preserved the `t594_7` note, updated to reference the new four-category layout.
  - Cross-references to `workflows/tmux-ide` redirected in 10 files (references about *launching* the IDE point to `installation/terminal-setup/`; references about *daily flow* point to `getting-started/`).
  - Removed the `tmux-ide → capturing-ideas` Next footer entry (gone with the file). Chain now starts at `capturing-ideas → retroactive-tracking → task-decomposition → task-consolidation (terminus)`.
- **Files affected:** 12 website files (1 deletion, 11 edits) + this plan file.

## Final Implementation Notes

- **Actual work done:**
  - Rewrote `workflows/_index.md` with the revised four-category structure (Tasks / Parallel / Review & Quality / Git). Kept the HTML comment noting t594_7 can consume these groupings as taxonomy source data.
  - Aligned `tmux-ide.md`'s `ait ide` snippet with `aitask_ide.sh` (documented `--session NAME`) — then deleted the page entirely per the revision. The command-reference content is already in `installation/terminal-setup.md`.
  - Added explore/fold cross-link to `task-decomposition.md` framing them as complementary patterns (explore for upfront, fold as inverse).
  - Added "Next:" footers across `capturing-ideas → retroactive-tracking → task-decomposition → task-consolidation` (terminus points back to the workflows index).
  - Redirected every `workflows/tmux-ide` cross-reference in the site.
- **Deviations from plan:** Original plan kept `tmux-ide.md` and only canonicalized its `ait ide` block. User's post-review direction deleted the page and restructured categories. Scope grew from 6 edited files to 1 deletion + 12 edited files.
- **Issues encountered:** Pre-existing uncommitted changes in `.claude/skills/aitask-explore/SKILL.md`, `.claude/skills/task-workflow/SKILL.md`, `.claude/skills/task-workflow/planning.md` are unrelated to t594_5 and were not staged.
- **Key decisions:**
  - Named the third category **Review & Quality** to capture `explain` naturally — understanding-driven reading supports quality review.
  - Redirect cross-refs to `installation/terminal-setup/` as the long-term home for `ait ide` command reference (it already has the full flag reference + shared-session gotcha). Walkthrough content from `tmux-ide.md` was not copied elsewhere — user's "eventually integrate" language was interpreted as deferring richer walkthrough integration.
- **Notes for sibling tasks:**
  - **t594_6 (concepts/commands/development sweep):** `concepts/ide-model.md` has a "How to use" section that now points to `terminal-setup` (was `tmux-ide`). Consider folding a short walkthrough into `ide-model.md` during the concepts sweep if a canonical daily-flow narrative is needed.
  - **t594_7 (Docsy labels):** the four workflow groupings (Tasks / Parallel / Review & Quality / Git) are candidate source data for a `workflow_category` taxonomy. The HTML-comment pointer in `_index.md` flags this explicitly.
  - A follow-up task may be warranted to migrate the deleted `tmux-ide.md` walkthrough content into `ide-model.md` or `getting-started.md` as a richer daily-flow narrative. Scope is out-of-bounds for this task per user's "eventually" framing.
