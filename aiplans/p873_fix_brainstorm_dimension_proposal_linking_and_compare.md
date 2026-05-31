---
Task: t873_fix_brainstorm_dimension_proposal_linking_and_compare.md
Base branch: main
plan_verified: []
---

# t873 — Fix brainstorm dimension↔proposal linking & compare (decomposition plan)

## Context

The `ait brainstorm` TUI has a cluster of related defects around **dimensions** —
how they link to proposals, render in the node detail pane, and feed the
`compare` operation. Surfaced and validated against live session 635
(`crew-brainstorm-635`: 8 nodes, 50 unique dimension keys, 26 `active_dimensions`).
Five distinct defects, sharing the dimension data model but **largely
independent**. The task author explicitly recommends splitting into 4 children
at planning time. Exploration confirms the diagnosis and that each fix has a
clean test/verification target.

**Recommendation: split into 4 sibling children** (matching the task's own
(a)/(b)/(c)/(d)), then accept the auto-offered aggregate manual-verification
sibling (this is TUI/UX-heavy and must be exercised against a live session).
No docs child (no `website/content/docs/tuis/brainstorm` page exists; these are
bug fixes to a WIP TUI, not a net-new documented feature). No retrospective
child (concrete bug fixes, not exploratory design-under-uncertainty).

Children auto-depend on siblings, so they run in order; **t873_1 is the shared
data-model foundation and goes first.**

## Decomposition

### t873_1 — Glob/prefix dimension-link expansion + badge-count fix + template tag hygiene  (defect 1)
Foundational. Today `get_sections_for_dimension` does an **exact** membership
test (`"component_foo" in ["component_*"]` is False), so glob section tags never
resolve and the `[N §]` badge counts the literal `"component_*"` string. The
explorer/detailer/initializer templates literally emit globs
(`[dimensions: component_*]`) and invented keys (`tradeoff_pros, tradeoff_cons`).

- **`.aitask-scripts/brainstorm/brainstorm_sections.py`**: add a match predicate
  supporting exact + prefix-glob (tag ending in `*` → `dim.startswith(tag[:-1])`)
  and rewrite `get_sections_for_dimension` to use it. Reconcile invented vs. real
  keys in `validate_sections` via an optional `node_keys` arg (glob tags stay
  valid; non-glob tags matching no real key flagged). Purely string-based — no
  node data needed for matching itself.
- **`.aitask-scripts/brainstorm/brainstorm_app.py:5020-5039`**: rewrite the
  `section_counts` loop in `_render_node_detail_widgets` to expand each section's
  tags against the node's real dimension keys (`dims` from `get_dimension_fields`,
  already in scope) and count **distinct sections per real key** (dedupe so a
  section tagging both `component_*` and `component_foo` isn't double-counted).
  `on_dimension_row_activated:5090` picks up the fix automatically via the helper.
- **Templates** (`templates/explorer.md`, `detailer.md`, `initializer.md`,
  `_section_format.md`): document that `prefix_*` globs are supported and expand;
  replace invented `tradeoff_pros/tradeoff_cons` with `tradeoff_*` (or "use real
  keys"). Templates are agent-run prompts, not skills — Claude-Code-first rule
  re skill porting does not apply.
- **Tests**: extend `tests/test_brainstorm_sections.py` (glob expansion in
  `get_sections_for_dimension`, validate-with-node-keys).

### t873_2 — Section scroll-to-position accuracy  (defect 2)
`SectionAwareMarkdown.scroll_to_section` (`.aitask-scripts/lib/section_viewer.py:268-289`)
uses a crude `start_line / total_lines` raw-source proportion over `max_scroll_y`;
on 373–709-line proposals it drifts off-target (HTML markers + section tags render
at different/zero heights). `estimate_section_y` already notes Textual's Markdown
"does not expose per-line offsets."
- **Fix direction** (implementer picks per installed Textual version): map each
  section to a **real rendered offset** — query the `Markdown` widget's child
  `MarkdownBlock` widgets, match the section's first rendered heading, and scroll
  via `scroll_to_widget` / the block's `.region.y`; or use Textual's
  `Markdown.goto_anchor(slug)` (heading-slug anchors) if available. Keep the
  existing `_poll_auto_scroll` deferral (blocks aren't laid out until rendered).
- **Tests**: `tests/test_section_viewer_filter.py` is the home; add a position-
  resolution unit test (mockable layer) where feasible — primary validation is
  manual (the mv sibling).

### t873_3 — Expandable / full-text dimension descriptions in detail pane  (defect 3)
`DimensionRow` (`brainstorm_app.py:1699-1756`) has CSS `height: 1` and `render()`
concatenates the full multi-sentence value into one clipped row, with no escape
hatch (the proposal-jump is unreliable per defects 1/2).
- **Fix**: add an `expanded` state toggled by a **distinct key** (Enter is taken
  by section-jump — use e.g. `space`); expanded → `height: auto` + wrapped full
  value. Follow the existing `on_key` pattern; per `aidocs/tui_conventions.md`
  ("footer must surface every operation"), surface the toggle (footer-visible
  `Binding` or a pane/row hint). Alternative: a small modal showing the full value.

### t873_4 — Compare wizard: scope to selected nodes, group, default to active_dimensions, descriptive labels  (defects 4 & 5)
`_config_compare` (`brainstorm_app.py:5644`) builds its dimension checklist from
`_get_all_dimension_keys()` (`:5749`) — a union of **every** node's keys (50 here),
deduped only by exact key, ungrouped, ignoring `active_dimensions`; labels are the
raw cryptic keys with no description.
- **Defect 4**: re-mount the dimension list scoped to **checked nodes** on
  selection change — mirror the existing `_refresh_compare_sections`/
  `_sections_intersection` pattern (`brainstorm_app.py:152-166`, `:5671`). Group by
  prefix via `group_dimensions_by_prefix` / `PREFIX_TO_LABEL`
  (`brainstorm_schemas.py:150`,`:24`). Default-check `active_dimensions` — **plumb a
  graph-state reader** from `brainstorm_dag` into the app (not currently imported).
- **Defect 5**: render each checkbox as `key — <description value>` (truncated);
  add a `_parse_dimension_label` (mirror `_parse_section_label`) so
  `_actions_collect_config` (`:5824`) recovers the raw key for `config["dimensions"]`.
- **Tests**: extend `tests/test_brainstorm_wizard_sections.py` (label parse-back,
  per-node scoping helper).

### t873_5 — (auto-offered) aggregate manual-verification sibling
Accept the workflow's post-creation offer, covering all 4 children: badge counts
+ glob links resolve (n005/n007/n008 stubs vs rich nodes), Enter lands on the right
proposal section on long proposals, dimension rows expand to full text, compare
wizard shows scoped+grouped+described dimensions defaulting to active_dimensions.
Verify against live session 635.

## Post-approval flow
On approval (Step 7 of the workflow), with write access restored:
1. Create t873_1..t873_4 via the Batch Task Creation Procedure, each with full
   Context / Key Files / Reference Files / Implementation Plan / Verification
   sections (Child Task Documentation Requirements).
2. Revert parent t873 → `Ready`, release parent lock.
3. Write `aiplans/p873/p873_{1..4}_*.md` plans; commit child plans together.
4. Accept the auto-offered aggregate manual-verification sibling (covers all 4).
5. Child checkpoint (always interactive): "Start first child" → `/aitask-pick 873_1`,
   or "Stop here".

## Verification
- Per-child unit tests via `bash tests/run_all_python_tests.sh` (targeting the
  three existing brainstorm test files).
- `shellcheck` n/a (Python-only changes); brainstorm launcher stays on
  `require_ait_python` (no fast-path change).
- End-to-end: `ait brainstorm` against the **existing** session
  `crew-brainstorm-635` (confirmed intact on disk: glob tags `component_*`/
  `assumption_*`, 6-line stub proposals n005/n007/n008, 373–709-line long
  proposals, 15 `component_*` + 13 `assumption_*` keys, 26 `active_dimensions`).
  **No regeneration needed** for the runtime fixes — all are read/render/query
  changes over the existing data; just reopen the session and observe corrected
  behavior. The aggregate mv sibling t873_5 drives this.
- **Only exception:** the *generation-side* half of t873_1 (template tag hygiene)
  needs one fresh brainstorm operation (e.g. a single `explore`/`detail`) to
  confirm newly-created proposals stop emitting invented/unexpandable tags — not
  a full session regenerate; largely covered by parser unit tests + template
  review, so the live agent run is optional.
