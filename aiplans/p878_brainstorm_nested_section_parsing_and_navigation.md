---
Task: t878_brainstorm_nested_section_parsing_and_navigation.md
Worktree: (none — profile 'fast', current branch)
Branch: main
Base branch: main
---

# t878 — Brainstorm nested section parsing & navigation

## Context

`ait brainstorm` renders agent-authored proposals/plans that are wrapped in
`<!-- section: name [dimensions: ...] -->` markers. The brainstorm templates
emit **nested** markers — a catch-all wrapper section containing many leaf
subsections:

- `explorer.md`: `<!-- section: components [dimensions: component_*] -->`
  wrapping `<!-- section: component_<name> [dimensions: component_<name>] -->`
- `detailer.md`: `<!-- section: step_by_step ... -->` wrapping
  `<!-- section: steps_<component_name> ... -->`

`parse_sections` (`.aitask-scripts/brainstorm/brainstorm_sections.py:56`) is
**non-reentrant**: the open guard `if open_m and cur_name is None` (line 74)
only opens a section when not already inside one, so every nested open marker
is swallowed as plain content of the outer section. The inner subsections are
never parsed as their own `ContentSection`.

User-visible effects (confirmed by t873_2 against `crew-brainstorm-635`): the
minimap lists only top-level sections, and activating a `component_X` dimension
from the node detail pane lands on the parent `## Components` heading instead of
that component's own `### X` subsection. (t873_1's glob expansion makes the link
*resolve* — the wrapper's `component_*` tag covers the key — but navigation
granularity is capped at the wrapper.)

Goal: parse nested sections as first-class `ContentSection`s, list them in the
minimap, and make dimension navigation land on the most-specific subsection.

## Key discovery — paths differ from the task description

The task references `section_viewer.correlate_sections_to_toc`. That module is
**`.aitask-scripts/lib/section_viewer.py`** (NOT under `brainstorm/`). It is a
**shared widget module** consumed by `board`, `codebrowser`
(`detail_pane.py`, `history_detail.py`) and `brainstorm` — so every change to it
must be **backward compatible** (new params with defaults; flat content must
parse identically).

## Approach

Represent nesting as a **flat, document-ordered list** of all sections (every
depth) with a `depth`/`parent` tag on `ContentSection`. This threads through the
existing consumers with minimal change: `correlate_sections_to_toc`'s monotonic
TOC pointer, `estimate_section_y`/`_section_positions` (keyed by `name` +
`start_line`), `_filter_sections`, and `get_sections_for_dimension` all already
iterate `parsed.sections` and key by name — they keep working once subsections
appear as their own entries in document order. A tree would force every consumer
to learn to recurse; the flat+depth model does not.

### 1. Parser — `.aitask-scripts/brainstorm/brainstorm_sections.py`

- **`ContentSection`** (line 20): add two fields at the **end** with defaults
  (backward compatible — only constructed via keywords in `parse_sections`):
  `depth: int = 0` and `parent: str | None = None`.
- **`parse_sections`** (line 56): rewrite the single-section state into a
  **stack** of open frames:
  - On an open marker: push a frame `{name, dims, start=lineno, content=[],
    depth=len(stack), parent=stack[-1].name if stack else None}`. Marker line is
    not added to any content (unchanged).
  - On a close marker **matching the top-of-stack name**: pop, append a
    `ContentSection` to results. A close that doesn't match the top falls
    through to content (robust against malformed/misordered closes — the
    `validate_sections` unclosed re-scan still flags those).
  - Content lines: append to the **innermost** open frame only (parent content
    excludes nested-subsection bodies — keeps each section's first heading clean
    so `_first_heading`/correlation resolve the right heading). Preamble/epilogue
    logic unchanged (`if stack: … elif not sections and last_close_idx == -1:
    preamble … else: epilogue`).
  - After the loop: `sections.sort(key=lambda s: s.start_line)` so results are in
    **document (open) order**, not close order. (Flat input is unaffected — open
    order == close order there.)
- **`validate_sections`** (line 124): keep duplicate-name detection **global** —
  section names must be globally unique for the name-keyed anchor map
  (`_section_anchors`) and `get_section_by_name` to work; nested subsection
  names in the templates are already unique (`component_<name>`,
  `steps_<component_name>`). The unclosed-section re-scan (regex `finditer` by
  name) already works with nesting. No behavior change needed; add a test that
  distinct nested names produce no false "Duplicate" error.
- **New helper `best_section_for_dimension(parsed, dimension)`**: return the
  most-specific section linked to a dimension — prefer an **exact** tag match
  over a glob match, then **deepest** `depth`, then earliest document order.
  Built on the existing `get_sections_for_dimension`. Used for nav targeting.

### 2. Shared viewer — `.aitask-scripts/lib/section_viewer.py`

- **`SectionRow.__init__`** (line 225): add `depth: int = 0`; in `render`
  (line 234) indent by depth (e.g. `"  " * depth` prefix) in both compact and
  expanded modes so the minimap shows hierarchy. Default 0 ⇒ unchanged for
  board/codebrowser callers.
- **`SectionMinimap.populate`** (line 305): pass `section.depth` to `SectionRow`.
- **`SectionViewerScreen.__init__`** (line 517): add
  `scroll_target: str | None = None`. In `on_mount` (line 535), the auto-scroll
  target becomes `scroll_target` if provided, else the existing
  `filtered[0].name` behavior (when a filter is active). Applied through the
  existing `request_scroll_to_section`. No change when neither is set.

### 3. Dimension navigation — `.aitask-scripts/brainstorm/brainstorm_app.py`

- **`on_dimension_row_activated`** (line 5089): after `matching =
  get_sections_for_dimension(parsed, event.dim_key)`, compute `best =
  best_section_for_dimension(parsed, event.dim_key)` and pass
  `scroll_target=best.name if best else None` to `SectionViewerScreen` (keep
  `section_filter=[s.name for s in matching]` so the minimap still shows the
  wrapper + leaf for context). Result: the viewer opens scrolled to the
  `component_X` subsection heading, with both rows in the minimap.

The inline minimap in `NodeDetailModal` (`populate(parsed)`, no filter) and its
`estimate_section_y` scroll (line 819) need **no change** — they already iterate
all `parsed.sections` and key by name+`start_line`, so subsections now appear
and scroll correctly for free.

## Intended side effects to surface at review

- **Dimension badge counts** (`brainstorm_app.py:5024-5038`): a `component_X`
  key is now matched by both the wrapper glob section *and* its own subsection,
  so its `section_count` badge increases (e.g. 1 → 2). This is more accurate
  (two sections genuinely cover the key) and is the direct consequence of
  parsing subsections — will flag it explicitly in Final Implementation Notes.
- **Compare wizard / section picker** (`_node_sections`, `_actions_show_section_select`,
  `_refresh_compare_sections`) now list subsections as additional, more granular
  selectable targets. Additive enhancement, no regression (they key on names).

## Files to modify

- `.aitask-scripts/brainstorm/brainstorm_sections.py` — parser stack, `depth`/
  `parent` fields, `best_section_for_dimension`.
- `.aitask-scripts/lib/section_viewer.py` — `SectionRow` depth indent,
  `populate` depth pass-through, `SectionViewerScreen.scroll_target`.
- `.aitask-scripts/brainstorm/brainstorm_app.py` — `on_dimension_row_activated`
  nav target.
- `tests/test_brainstorm_sections.py` — new `TestNestedSections` (+ a nested
  `correlate_sections_to_toc` case).

## Verification

Run the affected unit suites (CPython):

```bash
python3 tests/test_brainstorm_sections.py
python3 tests/test_section_viewer_filter.py
python3 tests/test_section_viewer_scroll.py
python3 tests/test_brainstorm_wizard_sections.py
```

New `TestNestedSections` coverage:
- nested parse → wrapper + leaves all present, correct `name`/`depth`/`parent`/
  `start_line`/`end_line`, **document order**; wrapper content excludes leaf
  bodies, each leaf content is its own.
- `get_sections_for_dimension("component_auth")` → wrapper + leaf;
  `best_section_for_dimension("component_auth")` → the **leaf**; for a
  glob-only dimension (e.g. `assumption_scale` with only `assumptions
  [assumption_*]`) → the wrapper.
- `validate_sections` on valid nested input → no errors (no false duplicate);
  unclosed nested leaf → flagged.
- `correlate_sections_to_toc` with nested sections → wrapper maps to its `##`
  heading, each leaf maps to its own `###` heading via the monotonic pointer.
- Existing flat tests still pass unchanged (regression guard).

Manual (offer as Step 8c manual-verification follow-up): in `ait brainstorm`
against a session with nested component subsections, open a `component_X`
dimension from the node detail pane → lands on the `### X` subsection; confirm
the minimap lists indented subsections.

## Post-implementation

Step 9 (current branch, profile 'fast'): no worktree/merge. Consolidate plan,
commit code (`bug: … (t878)`) + plan separately, then archive via
`./.aitask-scripts/aitask_archive.sh 878` and `./ait git push`.

## Final Implementation Notes

- **Actual work done:** Implemented exactly as planned across three source
  files + two test files.
  - `brainstorm_sections.py`: `parse_sections` rewritten from a single
    open-section state to a `_OpenFrame` **stack**; content accumulates into the
    innermost open frame, completed sections are `sort`ed by `start_line` for
    document order. `ContentSection` gained `depth`/`parent` (defaulted, so
    keyword construction stays compatible). New `best_section_for_dimension`
    ranks matches exact-tag-then-deepest for nav targeting.
  - `section_viewer.py` (shared widget): `SectionRow` gained `depth` and indents
    `"  " * depth`; `SectionMinimap.populate` passes `section.depth`;
    `SectionViewerScreen` gained `scroll_target` (overrides the default
    first-filtered auto-scroll).
  - `brainstorm_app.py`: `on_dimension_row_activated` now computes
    `best_section_for_dimension` and passes it as `scroll_target` (minimap filter
    still lists wrapper + leaf for context).
- **Deviations from plan:** None. Adopted "content model B" (wrapper content
  excludes subsection bodies) as planned — simpler and keeps each section's
  first heading correct for `correlate_sections_to_toc`.
- **Issues encountered:** None. All four affected suites pass
  (`test_brainstorm_sections` 39, `test_section_viewer_filter` 5,
  `test_section_viewer_scroll` 27, `test_brainstorm_wizard_sections` 16).
  Backward-compat confirmed: board/codebrowser only call `populate(parsed)` /
  `SectionViewerScreen(...)` — new params default safely; flat content is
  unchanged (`test_flat_input_unaffected`).
- **Key decisions:** Flat document-ordered section list + `depth`/`parent` tag
  (not a tree) so the existing consumers — `correlate_sections_to_toc`'s
  monotonic TOC pointer, `estimate_section_y`, `_filter_sections`,
  `get_sections_for_dimension` — keep working unchanged. Duplicate-name
  detection kept **global** (names must be globally unique for the name-keyed
  anchor map / `get_section_by_name`); template subsection names
  (`component_<name>`, `steps_<component_name>`) are already unique.
- **Intended side effect (surfaced at review, user approved "it's good"):**
  dimension **badge counts** (`brainstorm_app.py:5024-5038`) now count both the
  wrapper glob section and a key's own subsection, so a `component_X` badge can
  rise (e.g. 1 → 2). This is the accurate consequence of parsing subsections.
  The compare wizard / section picker likewise gain subsections as finer-grained
  selectable targets (additive, keyed on names). Both were offered as tunable at
  review and accepted as-is.
- **Upstream defects identified:** None.
- **Manual verification:** Live TUI behavior (open a `component_X` dimension →
  lands on the `### X` subsection; minimap lists indented subsections) is best
  validated by a human against a real nested session — offered as a Step 8c
  manual-verification follow-up.
