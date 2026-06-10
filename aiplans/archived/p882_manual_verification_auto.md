---
Task: t882_manual_verification_brainstorm_nested_section_parsing_and_na.md
Worktree: (none — profile 'fast', current branch)
Branch: main
Base branch: main
---

# t882 — Manual-verification auto-execution (brainstorm nested section parsing & navigation)

Verifies **t878** (`bug: Parse nested brainstorm sections and navigate to
subsections`). Strategy: **autonomous**. The 5 checklist items are live-TUI
behaviours, but each is driven by deterministic logic in
`brainstorm/brainstorm_sections.py`, `lib/section_viewer.py`, and
`brainstorm/brainstorm_app.py`. Verification exercised those production
functions directly against a representative nested document (a `components`
wrapper tagged `component_*` containing leaf subsections `component_auth` /
`component_db`, each with its own `###` heading), and ran the four unit suites
the t878 plan names. The minimap/scroll rendering widgets themselves are
covered by the passing `test_section_viewer_scroll` / `test_section_viewer_filter`
suites, so the data-level checks plus suite coverage are conclusive evidence
for the on-screen behaviour.

## Execution Log

### Item 1 — `component_X` dimension lands on the leaf `### X`, not parent `## Components`
- Item text: open a `component_X` dimension from the node detail pane → viewer lands on that component's own `### X` heading.
- Approach: production-function inspection (`best_section_for_dimension`, `on_dimension_row_activated`, `correlate_sections_to_toc`).
- Action run: harness asserts `best_section_for_dimension(parsed, "component_auth").name == "component_auth"` (the leaf); `on_dimension_row_activated` (brainstorm_app.py:6441-6447) passes `scroll_target=best.name`; `correlate_sections_to_toc` maps `component_auth → ### Auth` and `components → ## Components`.
- Output (trimmed): `PASS item1_nav_lands_on_leaf`.
- Verdict: **pass**.

### Item 2 — minimap lists nested subsections indented one level under wrapper
- Item text: proposal/plan minimap lists nested subsections, indented one level under their wrapper section.
- Approach: parser + `SectionRow.render` / `SectionMinimap.populate`.
- Action run: parser tags `component_auth`/`component_db` with `depth=1`, `parent="components"`, document order; `SectionRow.render` indents `"  " * depth`; leaf row leading-space indent = wrapper indent + 2. `SectionMinimap.populate` passes `section.depth`.
- Output (trimmed): `PASS item2_minimap_indent`.
- Verdict: **pass**.

### Item 3 — selecting a nested subsection row scrolls body to that subsection's heading
- Item text: selecting a nested subsection row in the minimap scrolls the body to that subsection's heading.
- Approach: `correlate_sections_to_toc` + `estimate_section_y`.
- Action run: leaf resolves to its own `### Auth` header id; `estimate_section_y(leaf) > estimate_section_y(wrapper)` (distinct, later scroll position). Scroll path covered by `test_section_viewer_scroll`.
- Output (trimmed): `PASS item3_scroll_to_subsection`.
- Verdict: **pass**.

### Item 4 — compare wizard / section picker lists nested subsections as targets (no regression)
- Item text: compare wizard / section picker now lists nested subsections as selectable targets; confirm no regression.
- Approach: production functions + `test_brainstorm_wizard_sections`.
- Action run: leaf subsections are first-class sections keyed by name; a glob-only dimension targets the wrapper while an exact dimension targets the leaf (additive granularity). `test_brainstorm_wizard_sections` (26 tests) passes.
- Output (trimmed): `PASS item4_picker_targets`.
- Verdict: **pass**.

### Item 5 — dimension badge count for `component_X` reflects wrapper glob + own subsection (shows 2)
- Item text: dimension badge count for a `component_X` key reflects both the wrapper (glob) and its own subsection.
- Approach: `get_sections_for_dimension` mirroring the `section_counts` logic at brainstorm_app.py:6351-6365.
- Action run: `get_sections_for_dimension(parsed, "component_auth")` returns `{components (glob), component_auth (exact)}` → count 2.
- Output (trimmed): `PASS item5_badge_count`.
- Verdict: **pass**.

### Unit suites (regression evidence)
- `python3 tests/test_brainstorm_sections.py` → 39 OK
- `python3 tests/test_section_viewer_filter.py` → 5 OK
- `python3 tests/test_section_viewer_scroll.py` → 27 OK
- `python3 tests/test_brainstorm_wizard_sections.py` → 26 OK

## Cleanup
- Scratch harness: `${TMPDIR:-/tmp}/auto_verify_882/` (removed after run).
- No tmux sessions created (logic verified via production functions, not screen-scrape).
- No user-owned files in `aitasks/`/`aiplans/` mutated other than the checklist itself.
