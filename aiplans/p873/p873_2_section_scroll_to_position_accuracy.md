---
Task: t873_2_section_scroll_to_position_accuracy.md
Parent Task: aitasks/t873_fix_brainstorm_dimension_proposal_linking_and_compare.md
Sibling Tasks: aitasks/t873/t873_3_expandable_dimension_descriptions_detail_pane.md, aitasks/t873/t873_4_compare_wizard_scope_group_label_dimensions.md, aitasks/t873/t873_5_manual_verification_fix_brainstorm_dimension_proposal_linkin.md
Archived Sibling Plans: aiplans/archived/p873/p873_1_glob_dimension_link_expansion_and_badge_count.md
Base branch: main
plan_verified:
  - claudecode/opus4_8 @ 2026-05-31 15:42
---

# Plan: t873_2 — Section scroll-to-position accuracy

Replace the crude raw-line-ratio scroll estimate in `SectionAwareMarkdown` with
a **real rendered-heading lookup** driven by Textual's own table of contents, so
jumping to a proposal section lands on that section's heading instead of an
off-by-screens proportional guess.

## Context

In the `ait brainstorm` node detail pane, pressing Enter on a dimension row opens
`SectionViewerScreen` and auto-scrolls to the linked proposal section. Today the
scroll target is a line-ratio guess: `ratio = section.start_line / total_lines`
then `target_y = ratio * max_scroll_y`
(`.aitask-scripts/lib/section_viewer.py:268-289`). Raw source line numbers count
hidden `<!-- section: … -->` markers and HTML comments that the Textual
`Markdown` widget renders at zero/different heights, so on the 373–709-line
session-635 proposals the target drifts and lands off-section (sibling t873_1
confirmed it currently stays at the top). The code already concedes the
limitation: `estimate_section_y` notes "Textual's `Markdown` widget does not
expose per-line offsets."

## Verification findings (live, against `crew-brainstorm-635`)

These were confirmed first-hand and shape the approach:

1. **Installed Textual is 8.2.7; `Markdown.goto_anchor` exists** — but it is
   **not** the right tool. It matches `TrackedSlugs().slug(title)` over the
   document's headings, and Textual **de-formats inline markdown in heading
   titles before slugging** (it stores `Orchestrator Skill — aitask-run-gates`,
   not the raw `` Orchestrator Skill — `aitask-run-gates` ``). A slug computed
   from a raw section heading therefore mismatches for any heading containing
   inline code/emphasis (real case: n000's `orchestrator` section). So we do
   **not** reconstruct slugs.
2. **The parser yields only top-level sections.** `parse_sections` is
   non-reentrant: n004 has 20 open/close tags but `parse_sections` returns **7
   sections** — nested `component_*` subsections are swallowed into the
   `components` section's content. The minimap therefore shows the clean
   top-level `## Heading` sections (Overview, Architecture, Data Flow,
   Components, …). Each parsed section's content reliably begins with a markdown
   heading (verified across n000/n001/n002×2/n004 — zero sections without a
   heading). Scrolling those is exactly what this task must fix; deep
   `component_*` navigation would need parser nesting and is **out of scope**
   (recorded under Final Implementation Notes).
3. **Section name ≠ heading title.** E.g. section `component_profile_template_registry`
   → heading "Profile-template registry — `…`". Resolution must use the
   section's first heading, recovered from `section.content`, not its name.
4. **Textual exposes the heading list publicly.** `Markdown.update()` async-parses
   and posts a public `Markdown.TableOfContentsUpdated` message carrying
   `table_of_contents` = `list[(level, title, header_id)]` in document order,
   with **de-formatted titles** and queryable `header_id`s
   (`md.query_one(f"#{header_id}")`). This is the authoritative, public source —
   captured via a message handler, no private-attr access, and it doubles as the
   "TOC ready" timing signal.
5. **Duplicate slugs exist in real data** (`workflow`×2 in n002, `motivation`/`gate-runs`×2
   in n000) but **never among the navigable top-level sections** — they are
   swallowed `###` subsections appearing *after* their parent's `##` heading.
   A monotonic document-order correlation handles even the theoretical collision.

## Approach

Capture Textual's TOC via the public message, correlate each parsed section to
its heading's `header_id` by an ordered (level + normalized-title) walk, and
scroll the heading block with `scroll_visible(top=True)` (bubbles to the outer
`SectionAwareMarkdown` `VerticalScroll`). Keep the existing ratio math as a
defensive fallback so nothing regresses when a heading can't be resolved.

## Key file

- `.aitask-scripts/lib/section_viewer.py` — `SectionAwareMarkdown`
  (`update_content`, `scroll_to_section`, new TOC handler + correlation) and
  `SectionViewerScreen._poll_auto_scroll` (readiness gate).

## Steps

1. **Pure correlation helpers (module-level, unit-testable, no widgets):**
   - `_first_heading(content) -> (level:int, title:str) | None` — first ATX
     heading in a section's content, skipping fenced code blocks
     (```` ``` ````/`~~~`). Level = count of leading `#`.
   - `_norm_title(s) -> str` — strip inline markdown Textual removes (backticks,
     `*`, `_`), collapse whitespace, lowercase. Used **only** for matching.
   - `correlate_sections_to_toc(sections, toc) -> dict[name -> header_id]` —
     walk `sections` in order with a monotonic pointer into `toc`; for each
     section, advance to the next `toc` entry whose `level` equals the section's
     first-heading level **and** `_norm_title(toc_title) == _norm_title(raw_heading)`;
     record `header_id`, advance the pointer past it. Sections whose heading
     isn't found are simply omitted (→ ratio fallback). The monotonic pointer
     makes duplicate titles resolve by position.

2. **`SectionAwareMarkdown` state:** add `self._toc = None` and
   `self._section_anchors: dict[str, str] = {}` in `__init__` (keep
   `_section_positions`, `_total_lines`, `_parsed` for fallback).

3. **`update_content`:** unchanged behavior plus reset `self._toc = None` and
   `self._section_anchors = {}` (the inner `Markdown.update()` will re-emit a
   fresh TOC).

4. **TOC capture handler:**
   ```python
   def on_markdown_table_of_contents_updated(
       self, event: Markdown.TableOfContentsUpdated
   ) -> None:
       self._toc = event.table_of_contents
       if self._parsed is not None:
           self._section_anchors = correlate_sections_to_toc(
               self._parsed.sections, self._toc
           )
       event.stop()
   ```
   (Handler name derives from `Markdown.TableOfContentsUpdated`; the message
   bubbles from the composed `Markdown` to its `SectionAwareMarkdown` parent.)

5. **`scroll_to_section(name)` — rewrite to anchor-first, ratio-fallback:**
   ```python
   hid = self._section_anchors.get(name)
   if hid:
       try:
           block = self.query_one("#section_md", Markdown).query_one(f"#{hid}")
           block.scroll_visible(top=True, animate=False)
           return
       except Exception:
           pass  # fall through to ratio fallback
   # existing ratio math unchanged (defensive)
   ```

6. **Timing (`SectionViewerScreen._poll_auto_scroll`):** gate readiness on the
   TOC being captured — `content._toc is not None` (replacing the
   `virtual_size.height > size.height` heuristic). Keep the attempt cap
   (`> 20` ≈ 2s) as a safety net and the existing deferral structure. The
   minimap-driven path (`on_section_minimap_section_selected`) is user-triggered
   and already post-render, so it needs no timing change.

7. **Tests** (`tests/test_section_viewer_filter.py` or a new
   `tests/test_section_viewer_scroll.py`, unittest, run via
   `bash tests/run_all_python_tests.sh`): cover `correlate_sections_to_toc` with
   a fake `toc` list of `(level, title, header_id)` tuples —
   (a) plain-title section → correct id; (b) **inline-code/emphasis heading**
   (raw `` `x` ``/`*x*` vs de-formatted toc title) → still matches;
   (c) **duplicate title** across two sections → monotonic pointer maps each to
   its own occurrence in order; (d) section whose heading is absent from `toc` →
   omitted (id falls back). Also test `_first_heading` skips fenced `#` lines and
   returns the right level/title.

## Verification

- `bash tests/run_all_python_tests.sh` (pre-existing unrelated failures
  `test_shortcut_scopes` / `test_desync_state` noted in t873_1 may persist; the
  section-viewer/brainstorm tests must pass).
- Manual (no regeneration), primary validation — covered by the t873 aggregate
  manual-verification sibling: `ait brainstorm` → session `crew-brainstorm-635`
  → n004 (709-line) → Enter on a dimension row whose section sits deep in the
  proposal → the viewer lands on that section's heading (top-aligned), not an
  off-by-screens position. Repeat on n002 variants (373/585-line). Confirm
  minimap row selection also lands accurately.

## Post-implementation

Follow task-workflow Step 8 (review/commit) and Step 9 (archival/merge). In
Final Implementation Notes record: the chosen TOC-correlation approach (and why
`goto_anchor` slug-matching was rejected — title de-format fragility); the
parser non-reentrancy scope limit (deep `component_*` subsections aren't
separately navigable — candidate follow-up); and any upstream defect surfaced.

## Post-Review Changes

### Change Request 1 (2026-05-31 16:05)
- **Requested by user:** After the accuracy fix, the auto-scroll on *opening* a
  proposal from a detail-pane dimension row still did nothing — the viewer
  stayed at the top. Asked whether that was expected.
- **Root cause (pre-existing, separate from the accuracy bug):**
  `SectionViewerScreen.on_mount` drove the deferred auto-scroll with
  `self.set_interval(0.1, self._poll_auto_scroll)`. The interval timer is
  created but its callback **never fires** from a freshly-pushed modal screen
  (reproduced: `attempts=0` after 3s of driven clock). So the pending scroll
  was never applied. The manual minimap-selection path worked because it calls
  `scroll_to_section` directly (no timer) — which is why accuracy improved there
  but on-open auto-scroll did not happen.
- **Changes made:** Replaced the poll-timer with an **event-driven** auto-scroll.
  `SectionAwareMarkdown.request_scroll_to_section(name)` records an active
  target; the `TableOfContentsUpdated` handler (which reliably fires) triggers
  `_apply_pending_scroll` via `call_after_refresh`. Because a long body lays out
  over several refresh cycles (the first `scroll_visible` lands mid-viewport —
  observed offset 29 vs target ~0), `_apply_pending_scroll` **re-applies the
  scroll across refreshes until the scroll offset stabilizes** (bounded to 5
  attempts), then clears the target. Removed `_poll_auto_scroll`,
  `_stop_auto_scroll`, and the `_pending_auto_scroll/_auto_scroll_attempts/
  _auto_scroll_timer` state from `SectionViewerScreen`.
- **Verification added:** New Pilot-driven integration tests in
  `tests/test_section_viewer_scroll.py` (`AutoScrollPilotTests`, synthetic
  proposal — no crew-data dependency): auto-scroll lands a deep section's
  heading at the top, an inline-code heading lands correctly, no-filter does not
  auto-scroll, and minimap selection scrolls. Confirmed live against
  `crew-brainstorm-635` n004/n002/n000 — every section (incl. deepest +
  inline-code `tooling`) lands at viewport-top offset ≤ 2.
- **Files affected:** `.aitask-scripts/lib/section_viewer.py`,
  `tests/test_section_viewer_scroll.py`.
