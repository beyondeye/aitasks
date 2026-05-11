---
Task: t764_only_main_tuis_in_main_web_page.md
Base branch: main
plan_verified: []
---

# Plan: t764 — Only main TUIs in main web page take-tour section

## Context

The website home page (`website/content/_index.md`) currently shows a "Take the tour" section listing five TUIs: Board, Code Browser, Monitor, Settings, and Stats, with a lead reading "Five TUIs share a single tmux session." The task asks to narrow the **tile list** down to only the three primary TUIs — **Board**, **Code Browser**, and **Monitor** — so the home page tour stays focused on the most-used surfaces, leaving the secondary TUIs (Settings, Stats, Brainstorm, etc.) to the broader `/docs/tuis/` index linked at the bottom of the section.

Per user clarification: the project actually ships **seven** TUIs (board, monitor, minimonitor, codebrowser, settings, brainstorm, stats), so the lead-paragraph count is currently understated. It should be updated to "Seven" — independent of how many tiles the tour shows.

## Scope

Single file: `website/content/_index.md`

Two edits inside the "Take the tour" `blocks/section` (lines 52–67):

1. **Lead paragraph** (line 55):
   - From: `<p>Five TUIs share a single tmux session. Click any of them to dive in.</p>`
   - To: `<p>Seven TUIs share a single tmux session. Click any of them to dive in.</p>`

2. **`.tour-mosaic` block** (lines 57–63): remove the Settings and Stats tour-tiles, keeping only Board, Code Browser, Monitor. Final block:

   ```html
   <div class="tour-mosaic">
   {{< tour-tile href="/docs/tuis/board/" src="imgs/home/board.svg" alt="Kanban board" caption="Board" >}}
   {{< tour-tile href="/docs/tuis/codebrowser/" src="imgs/home/codebrowser.svg" alt="Code browser" caption="Code Browser" >}}
   {{< tour-tile href="/docs/tuis/monitor/" src="imgs/home/monitor.svg" alt="Monitor TUI" caption="Monitor" >}}
   </div>
   ```

The "See all TUIs →" link below the mosaic is left unchanged.

## Explicitly out of scope

- The earlier feature card at line 22–24 (`fa-terminal` "Agentic IDE in your terminal") mentions "Kanban Board, Code Browser, Monitor, Brainstorm, and Settings" — the task is specifically about the **take-tour section**, not that feature card. Leave it untouched.
- No image/SVG changes; `imgs/home/settings.svg` and `imgs/home/statistics.svg` remain in `static/imgs/home/` (still referenced from `/docs/tuis/`).

## Verification

1. Re-read `website/content/_index.md` and confirm only the two edits above were applied.
2. Run a local Hugo dev server build and visually verify:
   ```bash
   cd website && ./serve.sh
   ```
   - Lead reads "Seven TUIs share a single tmux session."
   - Tour mosaic shows exactly three tiles (Board, Code Browser, Monitor).
3. Confirm "See all TUIs →" link still works and lands on the full TUIs index.

## Post-Implementation

Follow Step 8 (User Review and Approval) and Step 9 (Post-Implementation / archival) of the task-workflow SKILL.md. Active profile: `fast` (`post_plan_action: ask`, so the post-plan checkpoint will be presented).

## Post-Review Changes

### Change Request 1 (2026-05-11 10:30)
- **Requested by user:** Tour tile row is not horizontally centered with only three tiles.
- **Root cause:** `.tour-mosaic` in `website/assets/scss/_styles_project.scss` used `grid-template-columns: repeat(5, 1fr)` at the `>=992px` breakpoint with a `max-width: 1200px`. With only three tiles, they occupied the first three of five tracks (left-aligned) and the grid container itself stretched to a width tuned for five tiles.
- **Changes made:**
  - Dropped the `>=992px` `repeat(5, 1fr)` media query block entirely so the `>=768px` `repeat(3, 1fr)` rule applies on all desktop widths.
  - Reduced `.tour-mosaic` `max-width` from `1200px` to `900px` so the three tiles render at a size comparable to the previous five-tile layout (auto margins continue to horizontally center the grid container within its section).
- **Files affected:** `website/assets/scss/_styles_project.scss`

## Final Implementation Notes

- **Actual work done:**
  - `website/content/_index.md` — trimmed the take-tour `tour-mosaic` block from five tiles to three (Board, Code Browser, Monitor); updated the lead from "Five TUIs" to "Seven TUIs".
  - `website/assets/scss/_styles_project.scss` — removed the `@media (min-width: 992px)` block that forced `repeat(5, 1fr)` on the `.tour-mosaic` grid; reduced `max-width` from `1200px` to `900px` so three tiles render at a comparable size to the previous five-tile layout and stay horizontally centered via the existing `margin: 1rem auto 0`.
- **Deviations from plan:** Original plan touched only `_index.md`. During Step 8 review the user reported the three tiles were left-aligned on desktop — root cause was the CSS grid having 5 tracks. The CSS edit was added as Change Request 1.
- **Issues encountered:** None beyond the centering issue, which was an oversight in the original plan (CSS audit was not part of scope).
- **Key decisions:**
  - Removed the `>=992px` 5-col media query entirely rather than retargeting it to `repeat(3, 1fr)` — the `>=768px` rule already provides 3 columns, so the explicit lg-breakpoint rule was redundant for the new tile count.
  - `max-width` chosen as `900px` to keep approximate per-tile width (≈ 290px) comparable to the previous layout (1200px / 5 ≈ 240px).
- **Upstream defects identified:** None

