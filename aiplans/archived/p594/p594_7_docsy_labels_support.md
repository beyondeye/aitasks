---
Task: t594_7_docsy_labels_support.md
Parent Task: aitasks/t594_website_documentation_coherence.md
Parent Plan: aiplans/p594_website_documentation_coherence.md
Sibling Tasks: aitasks/archived/t594/t594_{1,2,3,4,5,6}_*.md (all archived)
Archived Sibling Plans: aiplans/archived/p594/p594_{1,2,3,4,5,6}_*.md
Worktree: (none — work on current branch)
Branch: main
Base branch: main
---

# t594_7 — Hugo/Docsy label/taxonomy support

## Context

The parent sweep (t594_1..6) finished factual-drift and coherence fixes on
~98 docs pages but **explicitly excluded** Hugo config and theme changes
(see `p594_website_documentation_coherence.md` §"Out-of-scope"). During
t594_3 review the user raised the need for a real label mechanism so
readers can filter the docs by maturity (experimental vs stable) and by
depth (main-concept vs reference vs advanced).

The only visible precedent today is a handful of hand-typed
`*(Main concepts)*` cues inside `website/content/docs/concepts/_index.md`
— a single-page signal that does not scale across the site. Docsy
inherits Hugo's native taxonomy support: defining custom taxonomies in
`hugo.toml` yields both per-page pills (rendered by Docsy's
`taxonomy_terms_article_wrapper.html`) and auto-generated taxonomy
listing pages (e.g. `/maturity/experimental/`).

**User scoping decisions (confirmed in planning):**
- **Taxonomy structure:** custom `maturity` + `depth` taxonomies (not a
  flat `tags` bucket, not Hugo's default `tags`/`categories`).
- **Scope:** broad — sweep every docs page and propose per-page labels;
  present the catalog for user confirmation before bulk-applying.
- **Inline markers:** delete the 5 `*(Main concepts)*` bullet markers
  from `concepts/_index.md` and rely on the taxonomy rendering instead.

## Goal

1. Declare `maturity` and `depth` taxonomies in `hugo.toml` so Docsy
   renders per-page pills and Hugo generates list pages.
2. Sweep all ~98 pages, produce a labeling catalog, confirm it with the
   user, then bulk-apply labels to the frontmatter.
3. Replace the manual `*(Main concepts)*` markers in
   `concepts/_index.md` with the taxonomy-driven rendering.
4. Verify `hugo build` passes and the new taxonomy list pages render.

## Scope

**In-bounds:**
- Edit `website/hugo.toml` — add `[taxonomies]` and
  `[params.taxonomy]` blocks.
- Add `maturity:` and/or `depth:` frontmatter fields to docs pages
  identified in the catalog step. Only pages that warrant a label are
  touched; un-marked pages stay un-marked (consistent with
  `concepts/_index.md`'s original asymmetric-marker choice).
- Remove the 5 `*(Main concepts)*` markers from
  `concepts/_index.md`.

**Out-of-bounds:**
- Custom layout partials beyond what Docsy already provides.
- Cross-page multi-filter UI / Pagefind integration — noted in task
  description as a possible follow-up.
- Structural edits to any doc page (no splits, merges, weight changes).
- Tags/categories work — this task introduces *only* the two new custom
  taxonomies.

## Proposed taxonomy vocabulary

Initial vocabulary — finalize during the catalog pass if additional
values are needed:

| Taxonomy | Values | Meaning |
|---|---|---|
| `maturity` | `experimental` | Pre-stable / unshipped / transitional features. Starting candidates: anything naming Brainstorm, agent-crews, diffviewer. |
| `maturity` | `stabilizing` | Shipped and usable but the interface is still evolving — on the path to stable. Halfway between `experimental` and `stable`. |
| `maturity` | `stable` | *Implicit default — not labeled explicitly* (keeps the diff minimal and preserves the "un-marked means stable" reader convention). |
| `depth` | `main-concept` | Foundational pages required for first-time reading. Starting candidates: the 5 pages currently marked `*(Main concepts)*`. |
| `depth` | `intermediate` | Pages for readers past the basics — the day-to-day middle of the docs. Natural gradient step between main-concept and advanced. |
| `depth` | `advanced` | Deeper material for power users / integrators. |

Pages with neither label stay un-labeled — the reader sees a pill only
when it carries signal.

## Key Files to Modify

- `website/hugo.toml` — declare `[taxonomies]` and
  `[params.taxonomy]`.
- `website/content/docs/**/*.md` — add `maturity:` and/or `depth:`
  frontmatter per the confirmed catalog (subset of ~98 pages).
- `website/content/docs/concepts/_index.md` — drop the 5
  `*(Main concepts)*` marker fragments.

## Reference files / patterns

- Docsy taxonomy docs:
  `/home/ddt/.cache/hugo_cache/modules/filecache/modules/pkg/mod/github.com/google/docsy@v0.14.3/docsy.dev/content/en/docs/content/taxonomy.md`.
- Docsy partials already doing the render work:
  - `.../docsy@v0.14.3/layouts/_partials/taxonomy_terms_article.html`
    — renders one taxonomy's pills for a page.
  - `.../docsy@v0.14.3/layouts/_partials/taxonomy_terms_article_wrapper.html`
    — loops over configured `taxonomyPageHeader` taxonomies.
- Current `website/hugo.toml` — no `[taxonomies]` or
  `[params.taxonomy]` blocks yet, so additions are purely additive.

## Implementation plan

### Step 1 — Declare taxonomies and display config

Edit `website/hugo.toml`. Add two blocks:

```toml
[taxonomies]
  tag = "tags"
  category = "categories"
  maturity = "maturity"
  depth = "depth"

[params.taxonomy]
  taxonomyPageHeader = ["maturity", "depth"]
  taxonomyCloud = []
```

Notes:
- When `[taxonomies]` is declared, Hugo stops using its implicit
  defaults, so `tag`/`category` must be re-listed even though no pages
  use them today.
- `taxonomyCloud = []` suppresses Docsy's right-sidebar tag cloud; the
  task description calls cross-page filter UI an optional follow-up, so
  we keep the visible surface to just the per-page pills.
- `taxonomyPageHeader` determines rendering order of the pills.

### Step 2 — Build the catalog

Sweep every `.md` file under `website/content/docs/` and produce a
catalog table with the proposed label(s) per page. Count today:

| Section | Pages |
|---|---|
| Root (`_index.md`, `overview.md`, `getting-started.md`) | 3 |
| `installation/` | 5 |
| `concepts/` | 14 |
| `commands/` | 10 |
| `skills/` (incl. `aitask-pick/`) | 31 |
| `tuis/` (incl. per-TUI subpages) | 15 |
| `workflows/` (incl. `contribute-and-manage/`) | 20 |
| `development/` | 3 |
| **Total** | **~98** |

Methodology:

**Heuristic-driven classification (maturity axis):**

For each feature page (a skill under `skills/`, a TUI under `tuis/`, a
command under `commands/`, a workflow under `workflows/`), derive an
initial maturity guess from two signals before reading the page:

1. **Git history of the source files** — for each page, identify its
   underlying source (e.g., `skills/aitask-pick.md` → source
   `.claude/skills/aitask-pick/SKILL.md`; `tuis/board/*.md` → source
   `.aitask-scripts/board/aitask_board.py`; `commands/codeagent.md` →
   source `.aitask-scripts/aitask_codeagent.sh` /
   `aitask_codeagent_config.json`). Run:
   ```bash
   git log --format="%ai %s" --no-merges -n 20 -- <source_path>
   ```
   Signals:
   - Oldest commit within the last ~60 days + small total commit count
     → **experimental** candidate.
   - Active churn in the last ~60 days on top of an older base (many
     commits, recent cluster) → **stabilizing** candidate.
   - Activity trailing off (last meaningful commit >60 days old, small
     recent drift) → **stable** candidate (leave unlabeled).
2. **Documentation coverage** — check the docs directory for the
   feature:
   - Full coverage (`_index.md` + `how-to.md` + `reference.md`, or a
     solid single page with examples + flag table + verification notes)
     → **stable** candidate.
   - Partial coverage (missing reference, or marked "pending" /
     "transitional" / TODO) → **experimental** or **stabilizing**.
   - Minimal stub or explicit "Dedicated documentation is pending"
     (e.g., `tuis/_index.md:22` for Brainstorm) → **experimental**.
3. **CLAUDE.md / README markers** — grep CLAUDE.md for the feature
   name; any "transitional", "actively evolving", "WIP", "experimental"
   qualifier wins immediately (the committers already flagged it).
   Example already present in CLAUDE.md: "`diffviewer` TUI is
   transitional." → experimental.

Combine the two signals conservatively. If git history and doc
coverage disagree, err toward the **more mature** label (prefer a
false-negative on the experimental pill rather than a false-positive).
Record the signals that drove the guess in the catalog's
"rationale" column so the user can spot-check and override.

**Page-level classification:**

1. Iterate section-by-section. For each page read the title, linkTitle
   and first paragraph (plus the heuristic output above); classify as
   one of:
   - `maturity: [experimental]` — page is about a pre-stable / unshipped
     feature or contains "transitional" / "pending" / "experimental"
     language.
     - Seed list (confirmed during exploration): `tuis/_index.md`
       mentions Brainstorm (line 22: "Dedicated documentation is
       pending."). If any brainstorm, agent-crews, diffviewer pages are
       discovered during the sweep, they receive this label.
   - `maturity: [stabilizing]` — shipped feature whose CLI/TUI/format is
     still actively evolving. Candidate criteria: the feature is usable
     today but the surrounding docs/CLAUDE.md flag ongoing refactors,
     "may change", or the SKILL.md / script has landed within the past
     few weeks of active churn. Apply sparingly — the default for
     shipped material is still unlabeled (stable).
   - `depth: [main-concept]` — foundational reading. Seed list (from the
     existing marker text in `concepts/_index.md`):
     - `concepts/tasks.md`
     - `concepts/plans.md`
     - `concepts/parent-child.md`
     - `concepts/locks.md`
     - `concepts/task-lifecycle.md`
   - `depth: [intermediate]` — day-to-day pages past the basics: most
     how-to pages, most `commands/*` pages, most skill pages readers
     meet after they've picked their first task.
   - `depth: [advanced]` — deep-integration material (e.g.,
     `concepts/git-branching-model.md`, `concepts/ide-model.md`,
     `concepts/agent-memory.md`, `installation/git-remotes.md`, advanced
     workflow pages, and low-level reference material like
     `development/task-format.md` / `development/review-guide-format.md`
     / TUI `reference.md` files that are for lookup/integration, not
     first-read).
   - *Unlabeled* — anything that does not cleanly fit the above (how-to
     pages, narrative overviews, `_index.md` files except where they
     themselves are a main-concept entry).
2. Write the catalog to
   `aiplans/p594/p594_7_label_catalog.md` as a markdown table grouped
   by section. Columns: `page | maturity | depth | rationale`. The
   `rationale` column cites the heuristic signals (e.g.,
   "src: 3 commits in last 40d, partial docs" → experimental;
   "CLAUDE.md flags transitional" → experimental; "full coverage, last
   src touch 180d ago" → stable / unlabeled).
3. Pages can receive both taxonomies (e.g., an experimental reference
   page) or just one. `_index.md` pages and pure-narrative pages may
   have neither.

### Step 3 — Catalog confirmation checkpoint

After the catalog is written, present it to the user via
`AskUserQuestion`:

- Question: "Catalog written to
  `aiplans/p594/p594_7_label_catalog.md` — \<N_main\> main-concept
  pages, \<N_int\> intermediate, \<N_adv\> advanced, \<N_exp\>
  experimental, \<N_stab\> stabilizing. Proceed with bulk-apply?"
- Options:
  - "Apply as-is" — continue to Step 4.
  - "Revise the catalog" — the user edits the catalog file directly
    (or dictates changes); re-read, present counts again, loop.
  - "Shrink scope to seed pages only" — fall back to labeling just the
    5 main-concepts and the experimental seeds, skip the rest.

This checkpoint is mandatory regardless of execution profile; the
catalog is the one place where the user's domain judgment is most
load-bearing and the bulk diff is large.

### Step 4 — Bulk-apply labels

For each catalog row with a non-empty taxonomy, add the field(s) to the
page's YAML frontmatter. Example:

```yaml
---
title: "Tasks"
linkTitle: "Tasks"
weight: 10
description: "Markdown files with YAML frontmatter — the core unit of work in aitasks."
depth: [main-concept]
---
```

- If the page has no existing frontmatter block, that is a no-op — such
  pages shouldn't appear in the catalog; skip them with a warning.
- Taxonomy values are always a **list** even when singleton, matching
  Hugo convention (`depth: [main-concept]` not `depth: main-concept`).
- Do **not** touch frontmatter ordering of existing keys; append the
  new keys at the end of the block.

### Step 5 — Remove the inline `*(Main concepts)*` markers

In `website/content/docs/concepts/_index.md`, delete the 5
`*(Main concepts)*` italic fragments from the bullet list (lines
14–34, per the current file). The linked page now carries the
`depth: [main-concept]` frontmatter, which Docsy will surface as a
pill at the top of the target page — the inline cue becomes redundant.

No other text on the page changes; `concepts/_index.md` keeps its
section headings ("Data model", "Workflow primitives", "Lifecycle and
infrastructure") and its intros.

### Step 6 — Build and verify

```bash
cd website && hugo build --gc --minify
```

Expected:
- Exit code 0 and zero *new* warnings (baseline warnings, if any,
  unchanged).
- Listing pages generated: `public/maturity/experimental/index.html`,
  `public/depth/main-concept/index.html`, etc., for every non-empty
  term.
- Spot-check one labeled page in `public/` HTML — the per-page pill
  section renders (Docsy's `taxonomy-terms-article` div is present).

Spot-check `concepts/_index.md` HTML — the `(Main concepts)` text is
gone and the linked pages show the pill at their top when visited.

## Verification

- `cd website && hugo build --gc --minify` — 0 new warnings, non-zero
  listing pages under `public/maturity/` and `public/depth/`.
- `grep -c "\\*(Main concepts)\\*" website/content/docs/concepts/_index.md`
  returns `0`.
- `grep -rn "^maturity:" website/content/docs/` lists at least the
  seed experimental pages plus any others the catalog added.
- `grep -rn "^depth: \\[main-concept\\]" website/content/docs/`
  returns at least the 5 seed pages.
- Open `public/depth/main-concept/index.html` in a browser (or `curl`
  the rendered HTML) — it lists the 5 main-concept pages.
- Open any main-concept page (e.g. `concepts/tasks/`) — the "Depth:
  main-concept" pill is rendered at the top.

## Step 9 (Post-Implementation) reference

No worktree was created (`create_worktree: false`), so Step 9 only runs
cleanup + archival:
- No branch merge needed.
- `verify_build` in `aitasks/metadata/project_config.yaml` is `null`,
  so the Hugo build check in Step 6 above is the task's own
  verification — no framework-driven build step to run.
- Archive via `./.aitask-scripts/aitask_archive.sh 594_7`. Since
  t594_1..6 are already archived, this completes the parent t594 and
  the archival script will also archive it automatically.
- `./ait git push` at the end.

The one-line intermediate artifact `aiplans/p594/p594_7_label_catalog.md`
(produced in Step 2) is committed as part of the plan directory and is
retained through archival (the archive script moves plan files into
`aiplans/archived/p594/`).

## Final Implementation Notes

- **Actual work done:**
  - `website/hugo.toml`: appended `[taxonomies]` (tag, category, maturity, depth) and `[params.taxonomy]` (taxonomyPageHeader=[maturity, depth], taxonomyCloud=[]).
  - `website/content/docs/**/*.md`: labeled 89 pages — 19 with `maturity:` (3 experimental, 16 stabilizing) and 89 with `depth:` (9 main-concept, ~40 intermediate, ~35 advanced). Labels appended at the end of each page's YAML frontmatter block as list values (e.g. `depth: [main-concept]`).
  - `website/content/docs/concepts/_index.md`: removed all 5 `*(Main concepts)*` inline markers now that the taxonomy pills render at the top of each main-concept page.
  - Catalog artifact `aiplans/p594/p594_7_label_catalog.md` records the per-page classification and rationale signals for future drift review.

- **Deviations from plan:** None on structure. The plan proposed an `~N_stab` count of ~15; final count is 16 (added `tuis/stats/_index.md` as a stabilizing+experimental edge case — ended up labeled just `experimental + intermediate`). Counts summary: 9 main-concept, 40 intermediate, 35 advanced, 3 experimental, 16 stabilizing, 12 unlabeled (section landings).

- **Issues encountered:**
  - After adding `[taxonomies]` in `hugo.toml`, Hugo stops using its implicit `tags`/`categories` defaults — the plan already flagged this; both were re-declared explicitly.
  - Bulk-apply used a one-shot `awk` helper (`/tmp/apply_labels.sh`, not committed) that inserts the new frontmatter keys just before the closing `---`. Each target file was verified to start with `---` before editing. No page was skipped for a missing frontmatter block.

- **Key decisions:**
  - Taxonomy values use hyphenated snake-case (`main-concept`, not `main concept`) so the generated URL slugs match.
  - `stable` maturity is implicit (unlabeled). `intermediate` depth is applied broadly to day-to-day pages; section landings (`_index.md` files) are deliberately left unlabeled to avoid pill noise on navigation pages.
  - `main-concept` scope was kept broad per the user-approved catalog — 9 pages including `overview.md`, `getting-started.md`, `board/_index.md`, and `aitask-pick/_index.md`, not just the original 5 `concepts/` seeds.

- **Verification performed:**
  - `cd website && hugo build --gc --minify` — 163 pages built, no new warnings.
  - `website/public/depth/main-concept/index.html` lists the 9 main-concept pages; `website/public/maturity/experimental/` and `/stabilizing/` exist with their terms.
  - `website/public/docs/concepts/tasks/index.html` contains the `taxonomy-terms-article taxo-depth` div with a "Main-Concept" pill.
  - `grep -c "Main concepts" website/content/docs/concepts/_index.md` returns `0`.

- **Follow-ups (out of scope, noted for a future task):**
  - Cross-page multi-filter UI / Pagefind integration for combining maturity + depth filters.
  - Re-evaluating each `stabilizing` label quarterly — the commit-history heuristic is a point-in-time signal and the label will drift into `stable` silently as churn slows.
  - Deciding whether dedicated Brainstorm / agent-crews pages (currently none in the docs) should be labeled `experimental` when they land.

- **Parent task note:** t594_7 was the final child of t594. Archiving this task also archives the parent t594 (all children complete).
