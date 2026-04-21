---
priority: medium
effort: medium
depends: []
issue_type: documentation
status: Done
labels: [documentation]
assigned_to: dario-e@beyond-eye.com
implemented_with: claudecode/opus4_7_1m
created_at: 2026-04-20 10:12
updated_at: 2026-04-21 09:58
completed_at: 2026-04-21 09:58
---

Add Hugo/Docsy label/taxonomy support to the website documentation, enabling pages to be tagged and filtered by label.

## Context

Raised during t594_3 (onboarding flow sweep) review. Sibling t594_3 added `*(Main concepts)*` markers to select bullets on `concepts/_index.md` as a lightweight visual cue. That pattern works for a single page but doesn't scale — readers can't filter "all main-concept pages across the docs" or "all experimental-feature pages" without infrastructure.

Docsy inherits Hugo's native taxonomies (`tags`, `categories`) and can define custom ones (`audience`, `skill_level`, etc.) via `config.toml` / `hugo.yaml`. Docsy renders tag pills at the top of each doc page and auto-generates taxonomy-listing pages (e.g., `/tags/main-concepts/`). Cross-page multi-filter UI is not built in but can be added with a small custom partial + JS (or Pagefind).

## Goals

1. **Sweep the website docs for labeling ideas.** Walk every content page under `website/content/docs/` and identify:
   - Candidate labels beyond `main-concepts` / `reference`.
   - Per-page label assignments (stored in frontmatter).
   - Example labels the user already has in mind: `experimental-feature` (for brainstorm, agent-crews, and other pre-stable features), `main-concepts`, `reference`, `advanced`.

2. **Decide on label taxonomies.** Choose which frontmatter fields to use:
   - Reuse Hugo's default `tags` taxonomy, or
   - Add dedicated custom taxonomies (e.g., `maturity` for experimental/stable, `depth` for main-concepts/reference/advanced) for cleaner separation.

3. **Apply labels site-wide.** Add the chosen frontmatter fields to every page that should carry a label. Do not over-label — leave pages unmarked when no signal is needed (consistent with t594_3's asymmetric marker decision on `concepts/_index.md`).

4. **Render labels in the theme.** Configure Docsy to render label pills at the top of each page (if not already the default), and ensure taxonomy list pages render.

5. **(Optional, could be a follow-up)** Add a cross-page label-filter UI to the top navigation or a dedicated `/docs/labels/` landing page so a reader can pick "experimental-feature" and see every experimental page at once.

## Key Files to Modify

- `website/hugo.yaml` (or `config.toml`) — declare custom taxonomies.
- `website/content/docs/**/*.md` — add label frontmatter fields.
- `website/layouts/` — if a custom label pill or filter UI is needed, overlay Docsy's defaults.

## Reference Pattern Files

- `website/content/docs/concepts/_index.md` — current manual marker pattern (`*(Main concepts)*`), set by t594_3. Labels would supersede this.
- Docsy's own documentation on taxonomy configuration (Hugo tags/categories).

## Labels to introduce (initial set — expand during sweep)

- `experimental-feature` — applied to brainstorm, agent-crews, diffviewer (transitional), and any other pre-stable feature pages.
- `main-concepts` — applied to the 5 foundational concepts already marked on `concepts/_index.md` (tasks, plans, parent-child, task-lifecycle, locks).
- `reference` — applied to detail-only / consult-as-needed pages.

## Implementation plan (sketch)

1. **Sweep** — read every page under `website/content/docs/`, catalog per-page label candidates.
2. **Present the catalog to the user** for label-vocabulary confirmation before bulk editing.
3. **Declare taxonomies** in `hugo.yaml`.
4. **Add frontmatter labels** to all pages (per the confirmed catalog).
5. **Replace the manual `*(Main concepts)*` markers on `concepts/_index.md`** with the label-driven rendering once the taxonomy renders.
6. **Hugo build check** — ensure taxonomy list pages render (e.g., `/tags/experimental-feature/`).

## Verification Steps

- `cd website && hugo build --gc --minify` — 0 new warnings.
- Click through a taxonomy list page (e.g., `/tags/experimental-feature/`) and confirm it lists the expected pages.
- Confirm `concepts/_index.md` renders correctly without the manual `*(Main concepts)*` markers (if replaced by label rendering).

## Notes

- Out-of-scope: client-side multi-filter UI (Pagefind integration). Can spawn as a later follow-up.
- The `experimental-feature` label is the user's highest-priority addition — brainstorm and agent-crews are unshipped/pre-stable and need to carry this badge visibly.
