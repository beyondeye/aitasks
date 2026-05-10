---
Task: t760_more_visually_appealing_home_page.md
Worktree: (none — working on current branch per `fast` profile)
Branch: main
Base branch: main
---

# Plan: more visually appealing home page (t760)

## Context

The current home page at `website/content/_index.md` is mostly a vertical
stack of text-only Docsy blocks: a logo-only cover hero, three icon-only
feature cards, an install table, and three text-only marketing sections
(task decomposition, code review, multi-agent). The framework's actual
UI — kanban board, code browser, settings tabs — never appears above
the fold despite a dozen high-quality SVG screenshots already living in
`website/static/imgs/`.

Reference site `https://getfresh.dev/` solves the same problem with a
**split hero** (text left, large UI screenshot right) and **inline
screenshots embedded in each feature section** so a first-time visitor
sees what the product *looks like* without scrolling forever.

This task brings the same pattern to aitasks: side-by-side hero with
the board view as the visual anchor, and inline TUI screenshots inside
each existing marketing section. Out of scope: changing the marketing
copy beyond minor adjustments to fit the new layout, redesigning
sub-pages, animations, dark-mode-specific styling.

## Approach

Low-risk, additive, no Docsy overrides. Four layers:

1. **New shortcode** `website/layouts/shortcodes/split-hero.html` —
   a self-contained side-by-side hero (text+image) that mirrors the
   visual weight of Docsy's cover block but supports a screenshot on
   the right at desktop widths and stacks vertically on mobile. The
   existing `blocks/cover` shortcode is kept as the outer wrapper so
   the navbar's `td-navbar-cover` translucent behavior continues to
   work (see `website/layouts/_partials/navbar.html:1-9`).

2. **Inline screenshots in feature sections** — use the existing
   `static-img` shortcode (with caption + zoom-on-click) inside each
   of the three marketing `blocks/section` blocks. One representative
   image per section. Same pattern as
   `website/content/docs/tuis/board/_index.md:12` and
   `website/content/docs/tuis/codebrowser/_index.md:12,16,20`.

3. **Small "Tour" mosaic** — a 2×2 / 1×4 grid of thumbnail screenshots
   directly above the install section. Each thumbnail links to its
   `/docs/tuis/...` page so the home page becomes a discoverable
   entry into the docs.

4. **SCSS polish** — extend `website/assets/scss/_styles_project.scss`
   with rules for `.split-hero` and `.tour-mosaic`. Reuse the existing
   `$primary` / `$secondary` brand colors. No JS, no animations.

The audit found `website/layouts/blocks/` does not exist and there are
no prior overrides, so this is a clean-slate addition with no collision
risk.

## Assets the user will provide

All new home-page imagery goes under a new directory:
**`website/static/imgs/home/`** (created during implementation if
absent).

The user will supply five new files. Expected filenames (rename in
plan and `_index.md` to match whatever the user actually drops in —
the user will tell us at implementation time):

| Slot                     | Suggested filename                       | Notes |
|--------------------------|------------------------------------------|-------|
| Hero (board)             | `imgs/home/board.svg`                    | Wide aspect (~1.5:1) preferred. |
| Task-decomp section      | `imgs/home/claude_task_decomposition.webp` | Captured from a Claude Code session that asked for task decomposition. WebP per user. |
| Code-review section      | `imgs/home/codebrowser.svg`              | New codebrowser TUI capture. |
| Multi-agent section      | `imgs/home/monitor.svg`                  | Monitor TUI showing live agent panes. |
| Stats / tour 4th tile    | `imgs/home/statistics.svg`               | Statistics TUI; used in the tour mosaic, replacing `codebrowser_task_history.svg` from the original draft. |

If a slot's file is missing at implementation time, fall back to the
existing SVG already in `website/static/imgs/` (i.e. preserve the
original draft) and note the substitution in the Final Implementation
Notes.

For the **tour mosaic**, the user picked "use existing SVGs", with one
adjustment: the 4th tile uses the new user-supplied
`imgs/home/statistics.svg` (a more representative top-level TUI than
task-history). The other three mosaic tiles continue to use existing
assets:
- `imgs/aitasks_board_main_view.svg` → `/docs/tuis/board/`
- `imgs/aitasks_codebrowser.svg` → `/docs/tuis/codebrowser/`
- `imgs/aitasks_settings_board_tab.svg` → settings docs (path TBD at impl time)
- `imgs/home/statistics.svg` → stats docs (path TBD at impl time)

## Files changed

### 1. New: `website/layouts/shortcodes/split-hero.html`

Custom shortcode rendering a flex/grid container with two children:
left column with `title`, `tagline`, `description`, two CTA buttons;
right column with a single `<img>` from `src` (relURL'd). Mobile
breakpoint stacks vertically. Honors the same `data-bs-theme` rules as
the Docsy cover block so the navbar's translucent-over-cover behavior
is preserved (see `website/layouts/_partials/navbar.html:1-9` — the
`HasShortcode "blocks/cover"` test). To preserve the translucent
navbar, the new shortcode emits an outer `<section
class="td-cover-block split-hero ...">` so Docsy's CSS still treats it
as a cover-style first block; we'll also wrap the home page invocation
in `{{< blocks/cover height="auto" color="primary" >}}` and place the
split-hero markup inside it. Decision: **simpler path** — keep the
existing `{{< blocks/cover >}}` outer (which handles the navbar
translucency contract correctly out of the box) and put the split-hero
shortcode *inside* it. The shortcode then only emits a
`<div class="split-hero-grid">` and inner content, no outer cover
wrapper.

Inputs (named params, all optional):
- `title` — bold heading text
- `lead` — one-line tagline (e.g. "A full agentic IDE in your terminal.")
- `description` — short paragraph below the lead
- `image` — path under `static/` (e.g. `imgs/aitasks_board_main_view.svg`)
- `image_alt` — accessibility text
- `cta_primary_text` / `cta_primary_href`
- `cta_secondary_text` / `cta_secondary_href`

Body (between open/close tags) is rendered as additional content under
the description, so future bullets can be added without changing the
shortcode.

### 2. Edit: `website/assets/scss/_styles_project.scss`

Append (file currently empty after the comment header):

```scss
// Split hero
.split-hero-grid {
  display: grid;
  grid-template-columns: 1fr;
  gap: 2rem;
  align-items: center;
  max-width: 1180px;
  margin: 0 auto;

  @media (min-width: 992px) {
    grid-template-columns: 1.05fr 1.25fr; // image slightly larger
  }

  .split-hero-text { text-align: left; }

  .split-hero-image {
    img {
      width: 100%;
      height: auto;
      border-radius: 8px;
      box-shadow: 0 12px 40px rgba(0, 0, 0, 0.45);
      background: #1a1a1a; // matches SVG terminal bg, hides any AA edges
    }
  }

  .split-hero-cta { margin-top: 1.25rem; }
}

// Tour mosaic
.tour-mosaic {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 1rem;
  margin: 1.5rem auto 0;
  max-width: 1100px;

  @media (min-width: 992px) {
    grid-template-columns: repeat(4, 1fr);
  }

  a {
    display: block;
    text-decoration: none;
    color: inherit;
    transition: transform 0.15s ease;
    &:hover { transform: translateY(-2px); }
  }

  figure {
    margin: 0;
    img {
      width: 100%;
      height: auto;
      border-radius: 6px;
      box-shadow: 0 4px 16px rgba(0, 0, 0, 0.25);
      background: #1a1a1a;
    }
    figcaption {
      text-align: center;
      font-size: 0.85rem;
      margin-top: 0.4rem;
      color: var(--bs-secondary-color, #555);
    }
  }
}

// Subtle gradient on cover for visual depth (replaces flat $primary)
.td-cover-block.split-hero-cover {
  background-image: linear-gradient(135deg, #5b21b6 0%, #1e3a8a 100%);
}
```

### 3. Edit: `website/content/_index.md`

Replace the current cover block (lines 6–18) with:

```hugo
{{< blocks/cover title="" image_anchor="top" height="auto" color="primary" class="split-hero-cover" >}}
{{< split-hero
    title="aitasks"
    lead="A full agentic IDE in your terminal."
    description="Kanban board, code browser, agent monitoring, and AI-enhanced git workflows — all in one tmux session. Press `j` to hop between TUIs without leaving the terminal."
    image="imgs/home/board.svg"
    image_alt="aitasks kanban board with three columns of task cards"
    cta_primary_text="Documentation"
    cta_primary_href="docs/"
    cta_secondary_text="⭐ Star on GitHub"
    cta_secondary_href="https://github.com/beyondeye/aitasks"
>}}{{< /split-hero >}}
{{< /blocks/cover >}}
```

(If `blocks/cover` doesn't accept a `class=` parameter — to be verified
against Docsy at implementation time by reading the upstream shortcode
or adding the class via the SCSS rule's parent selector instead — fall
back to plain `color="primary"` and apply the gradient to the
`td-cover-block` selector globally on the home page only via a
body-class check or a `:has()` selector targeting `.split-hero-grid`.)

Then **insert inline screenshots** into each marketing section using
the existing `static-img` shortcode. Concretely:

- After the **Task decomposition & parallelism** heading (currently at
  line 53), insert before the bullet list:
  ```hugo
  {{< static-img src="imgs/home/claude_task_decomposition.webp" alt="A Claude Code session decomposing a complex task into child subtasks" caption="A live agent decomposing a complex task into well-scoped child subtasks." >}}
  ```

- After the **AI-enhanced code review** heading (line 70), insert:
  ```hugo
  {{< static-img src="imgs/home/codebrowser.svg" alt="Code browser annotated with task history and detail pane" caption="Code browser annotates each line back to the originating task and plan." >}}
  ```

- After the **Multi-agent support with verified scores** heading (line
  83), insert:
  ```hugo
  {{< static-img src="imgs/home/monitor.svg" alt="Monitor TUI showing multiple live agent panes" caption="Watch multiple agents work side-by-side in the monitor TUI." >}}
  ```

- **Insert a new "Take the tour" mosaic section** between the install
  block (currently ending at line 50) and the task decomposition block.
  Use a `blocks/section` wrapper so spacing matches the rest of the
  page, then a custom HTML `<div class="tour-mosaic">` with four
  `<a><figure>` items linking to:
  - `/docs/tuis/board/` — `imgs/aitasks_board_main_view.svg`
  - `/docs/tuis/codebrowser/` — `imgs/aitasks_codebrowser.svg`
  - settings docs page — `imgs/aitasks_settings_board_tab.svg`
  - stats docs page — `imgs/home/statistics.svg`

  Implementation note: at implementation time, run
  `find website/content/docs/tuis -maxdepth 2 -name '_index.md'` to
  enumerate existing TUI doc pages, then resolve the settings and stats
  link targets to real pages. If a target doesn't exist, fall back to
  `/docs/tuis/`.

### 4. (Optional, only if Hugo build flags warnings) — adjust hero markdown

The current `_index.md` lead line and "Star on GitHub to support us!"
copy is preserved verbatim inside the `split-hero` shortcode params.
No new copy unless a string fails to render.

## Reusable existing pieces

- **`static-img` shortcode** (`website/layouts/shortcodes/static-img.html`)
  — already provides zoom-on-click, captions, and per-page CSS+JS
  injected once via `Page.Store`. Reuse for all inline feature
  screenshots and tour-mosaic thumbnails.
- **Brand colors** (`website/assets/scss/_variables_project.scss:2-3`)
  — `$primary: #7C3AED` and `$secondary: #1E40AF` drive the gradient
  endpoints; do not introduce new variables.
- **Docsy `blocks/cover` and `blocks/section`** — keep as outer
  wrappers; we add inside, not around.

## Verification

1. **Build the site locally**:
   ```bash
   cd website && ./serve.sh
   ```
   Open `http://localhost:1313/` in a browser.

2. **Visual checks (manual)**:
   - Hero: title + lead + description on the left, board screenshot
     prominent on the right at ≥992px viewport. Stacks vertically on
     <992px (test by resizing the window).
   - Hero gradient is smoothly applied (no flat fallback color
     leaking).
   - Three feature sections each have a screenshot above their text
     content; click an image — `static-img` overlay opens; press
     `Esc` — overlay closes.
   - Tour mosaic shows 4 thumbnails in a row at desktop, 2×2 at
     tablet, 1 column on mobile. Each thumbnail is clickable and
     navigates to a real docs page (no 404s).
   - Navbar still becomes translucent over the hero (Docsy
     `td-navbar-cover` behavior), and becomes opaque on scroll.
   - Existing sections below the hero (install table, releases) are
     unchanged and render normally.
   - Page works with the dark/light theme toggle (no contrast
     regressions on either).

3. **Hugo build sanity** — production build must complete with no
   new warnings:
   ```bash
   cd website && hugo build --gc --minify
   ```
   Then `grep -i warning` the build log.

4. **Markdownlint** — `_index.md` should still parse as valid
   Hugo/markdown; no new shortcode errors at startup.

## Step 9 (Post-Implementation)

Per workflow: review change summary, commit code changes (regular
`git`) and the plan file (`./ait git`) separately, push, then archive
via `./.aitask-scripts/aitask_archive.sh 760`. Issue type
`documentation` → commit subject:
`documentation: Redesign home page with split hero and inline TUI screenshots (t760)`.
