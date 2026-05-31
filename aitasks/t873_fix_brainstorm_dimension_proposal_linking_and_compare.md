---
priority: high
effort: medium
depends: []
issue_type: bug
status: Ready
labels: [brainstorming, ait_brainstorm, ui]
children_to_implement: [t873_2, t873_3, t873_4, t873_5]
created_at: 2026-05-31 12:44
updated_at: 2026-05-31 14:10
---

Fix a cluster of related defects in the `ait brainstorm` TUI around **dimensions** — how they link to proposals, how they render in the node detail pane, and how they feed the `compare` operation. Surfaced while using session 635 (`crew-brainstorm-635`); validated against its real data (8 nodes, 50 unique dimension keys, 26 `active_dimensions`).

## Background — how dimension↔proposal linking works today

- A graph node (`br_nodes/nXXX.yaml`) has dimension fields keyed `requirements_*` / `assumption_*` / `component_*` / `tradeoff_*` (prefixes in `brainstorm_schemas.py:21`). The key **suffix** is a short handle; the **value** is the (usually long) description.
- A proposal (`br_proposals/nXXX.md`) links a dimension by tagging a section: `<!-- section: NAME [dimensions: KEY1, KEY2] -->` (parsed in `brainstorm_sections.py`).
- The node **detail pane** renders one `DimensionRow` per dimension with a `[N §]` badge (`brainstorm_app.py:5017-5039`, `DimensionRow` at `:1699-1756`). Enter on a row calls `get_sections_for_dimension()` and pushes `SectionViewerScreen` scrolled to the first matching section (`brainstorm_app.py:5077-5102`).

## The defects

### 1. Many dimensions have no link to the proposal (`[0 §]`)
Two distinct causes, both confirmed:
- **Stub proposals:** explorer/synthesizer nodes (e.g. `n005`, `n007`, `n008`) have 6-line proposals with **zero section markers**, so every dimension shows `[0 §]`.
- **Glob tags are never expanded:** rich proposals tag catch-all sections like `<!-- section: components [dimensions: component_*] -->`, `[dimensions: assumption_*]`, `[dimensions: tradeoff_*]`. But `get_sections_for_dimension` (`brainstorm_sections.py:174`) does an **exact** membership test: `"component_foo" in ["component_*"]` is `False`. There is **no glob/prefix expansion anywhere**. So a dimension covered *only* by a glob section gets no link, and the badge counter (`brainstorm_app.py:5024-5026`) counts the literal string `"component_*"` instead of the real keys. `validate_sections` even passes these because `is_dimension_field("component_*")` returns True. Agents also sometimes invent tags (`tradeoff_pros`/`tradeoff_cons`) that match no real node key.

**Fix direction:** expand `*` globs (and/or prefix wildcards) in `get_sections_for_dimension` and in the `section_counts` loop; reconcile invented tags vs. real node keys (possibly validate section tags against the node's actual dimension keys at generation time in the explorer/synthesizer/detailer templates).

### 2. Links that exist resolve to the wrong proposal position
`SectionViewer` computes the scroll target as `ratio = section.start_line / total_lines` then `target_y = ratio * max_scroll_y` (`lib/section_viewer.py:273-275, 277-289`). This is a **crude proportional estimate over raw source line numbers** — including hidden HTML-comment markers and section tags the Markdown widget renders at different (or zero) heights. On 373–709-line proposals the target drifts noticeably and lands off the intended section.

**Fix direction:** map the section to a real rendered offset (e.g. track the Markdown widget's per-block/heading offsets, or anchor on the first rendered heading inside the section) instead of a raw-line proportion.

### 3. Long dimension descriptions are truncated with no way to see the full text
`DimensionRow` CSS sets `height: 1` (`brainstorm_app.py:1713`) and `render()` (`:1746`) concatenates the full value into that single clipped row. Real values are multi-sentence. The intended "read the full description" escape hatch is the proposal jump — but per #1/#2 that link is usually missing or mis-targeted, so there is effectively **no way to read the full dimension description**.

**Fix direction:** allow expanding a row (wrap to multiple lines / toggle), and/or show the full value in the detail pane area or a popup; ensure a reliable path to the description independent of proposal section tagging.

### 4. The compare dimension list is too long to define a meaningful comparison
The compare wizard's dimension step (`_config_compare` at `brainstorm_app.py:5644`, dimensions at `:5653-5658`) builds its checklist from `_get_all_dimension_keys()` (`:5749-5759`), which **unions every node's dimensions across the whole graph** (50 unique keys here; individual nodes carry 23–45), deduped only by exact key. No grouping, no scoping to the selected nodes, and `active_dimensions` is ignored.

**Fix direction:** scope candidate dimensions to the nodes actually selected for comparison (intersection/union of just those), and/or group by prefix, and/or default to `active_dimensions`; consider collapsing by prefix with expand-on-demand.

### 5. The compare wizard shows the cryptic key, not the dimension's meaning
The checklist labels are the raw dimension keys (e.g. `component_profile_template_registry`) — built at `brainstorm_app.py:5653-5658` and collected at `:5823-5824`. The descriptive **value is never surfaced**, and there is no "full name" registry (`active_dimensions` is just a flat list of keys; `PREFIX_TO_LABEL` only labels the group). This makes it hard to pick meaningful dimensions.

**Fix direction:** include the dimension's description value (and/or a human label) in each checklist entry; if a richer name is wanted, decide where it lives (node value vs. a new registry field).

## Files in scope
- `.aitask-scripts/brainstorm/brainstorm_app.py` — detail pane (`_render_node_detail_widgets`, `DimensionRow`, `on_dimension_row_activated`), compare wizard (`_config_compare`, `_get_all_dimension_keys`)
- `.aitask-scripts/brainstorm/brainstorm_sections.py` — `get_sections_for_dimension`, glob expansion, `validate_sections`
- `.aitask-scripts/lib/section_viewer.py` — scroll-to-section position math
- `.aitask-scripts/brainstorm/brainstorm_schemas.py` — dimension prefixes / labels (if a full-name concept is added)
- `.aitask-scripts/brainstorm/templates/{explorer,synthesizer,detailer,comparator}.md` — proposal/section-tag generation guidance (to stop emitting unexpandable globs / mismatched tags)

## Notes
- Consider splitting into children at planning time: (a) linking/glob-expansion + count fix, (b) scroll-resolution fix, (c) detail-pane truncation/expand, (d) compare-wizard scoping + descriptive labels. They share the dimension model but are largely independent.
- Per framework convention, any skill/template wording changes here are Claude-Code-first; mirror to Codex/OpenCode as follow-ups if applicable. (The brainstorm templates are agent-run prompts, not skills.)
