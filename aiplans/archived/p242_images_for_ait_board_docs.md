---
Task: t242_images_for_ait_board_docs.md
Worktree: (none — working on current branch)
Branch: main
Base branch: main
---

## Context

The `ait board` documentation in the Hugo/Docsy website has 8 HTML comment placeholders for screenshots but no actual images. Four SVG images now exist in `imgs/` that match specific placeholders. The task is to place each image exactly once in the most appropriate location and verify the Hugo build.

## Plan

### 1. Copy SVG images to Hugo static directory

Copy the 4 SVG files from `imgs/` to `website/static/imgs/`:
- `aitasks_board_main_view.svg`
- `aitasks_board_task_detail.svg`
- `aitasks_board_commit.svg`
- `aitasks_board_customize_column.svg`

### 2. Replace placeholders with images (each image placed once)

**`website/content/docs/board/_index.md`:**
- Line 10: Replace `<!-- SCREENSHOT: Full board overview -->` with `aitasks_board_main_view.svg`
- Line 31: Keep placeholder (annotated layout — no matching image yet)
- Line 55: Keep placeholder (task card close-up — no matching image yet)

**`website/content/docs/board/how-to.md`:**
- Line 28: Replace `<!-- SCREENSHOT: Column edit dialog -->` with `aitasks_board_customize_column.svg`
- Line 68: Replace `<!-- SCREENSHOT: Task detail dialog -->` with `aitasks_board_task_detail.svg`
- Line 114: Replace `<!-- SCREENSHOT: Commit message dialog -->` with `aitasks_board_commit.svg`
- Line 158: Keep placeholder (expanded children — no matching image yet)
- Line 211: Keep placeholder (lock status — no matching image yet)

### 3. Image markup format

Use a custom `static-img` shortcode with Hugo's `relURL` for correct path resolution and click-to-zoom lightbox.

### 4. Verify Hugo build

Run `hugo build --gc --minify` in `website/` and confirm clean build.

## Final Implementation Notes
- **Actual work done:** Copied 4 board SVG images to `website/static/imgs/`, created `static-img` shortcode with `relURL` resolution and click-to-zoom lightbox, replaced 4 screenshot placeholders with shortcode calls, removed original SVGs from root `imgs/`.
- **Deviations from plan:** Initially used Hugo's built-in `figure` shortcode, but it doesn't apply `relURL` to `src`, causing 404s when the site is served under a subdirectory (`/aitasks/`). Created a custom `static-img` shortcode instead. Also added click-to-zoom lightbox per user request (overlay with close button, Escape key support).
- **Issues encountered:** Hugo's `figure` shortcode outputs `src` as-is without `relURL` processing, breaking paths when `baseURL` has a path prefix. Fixed by creating custom shortcode with `relURL` pipe. Also fixed duplicate `class` attribute bug in the shortcode template.
- **Key decisions:** Used `.Page.Store` to ensure CSS/JS is only injected once per page. Kept remaining 4 placeholders for future images.
