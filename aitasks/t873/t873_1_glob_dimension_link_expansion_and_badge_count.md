---
priority: high
effort: medium
depends: []
issue_type: bug
status: Ready
labels: [brainstorming, ait_brainstorm, ui]
created_at: 2026-05-31 13:12
updated_at: 2026-05-31 13:12
---

Fix the foundational dimension↔proposal linking defect (defect #1 of parent t873): glob/prefix dimension tags never resolve, and the `[N §]` badge counts the literal glob string instead of real keys. Also clean up the agent templates that emit unexpandable globs and invented tag keys.

## Context
A proposal links a dimension by tagging a section: `<!-- section: NAME [dimensions: KEY1, KEY2] -->`. Rich proposals use catch-all globs like `[dimensions: component_*]` / `[dimensions: assumption_*]`. But `get_sections_for_dimension()` does an **exact** membership test (`"component_foo" in ["component_*"]` is `False`), so a dimension covered *only* by a glob section gets no link and shows `[0 §]`. The detail-pane badge counter (`brainstorm_app.py:5024-5026`) counts the literal string `"component_*"` as if it were a key. `validate_sections` even passes glob tags because `is_dimension_field("component_*")` returns True. Agents also invent tags (`tradeoff_pros`/`tradeoff_cons`) that match no real node key — the explorer/detailer/initializer **templates literally instruct this**.

This is the shared data-model fix the other t873 children build on, so it is child 1 and runs first. Validated against live session `crew-brainstorm-635` (`.aitask-crews/crew-brainstorm-635/`): its proposals contain real `[dimensions: component_*]`, `[dimensions: assumption_*]`, `[dimensions: assumption_*, requirements_*]` tags, plus 6-line stub proposals (n005/n007/n008) with zero markers.

## Key Files to Modify
- `.aitask-scripts/brainstorm/brainstorm_sections.py` — add a tag-match predicate; rewrite `get_sections_for_dimension` (currently line 170-174); extend `validate_sections` (line 124-152) to accept an optional `node_keys` arg that flags non-glob tags matching no real key (keep glob tags valid).
- `.aitask-scripts/brainstorm/brainstorm_app.py:5017-5039` — rewrite the `section_counts` loop in `_render_node_detail_widgets` so each section's tags are expanded against the node's real dimension keys (`dims = get_dimension_fields(node_data)`, already in scope at :5017), counting **distinct sections per real key** (dedupe: a section tagging both `component_*` and `component_foo` must count once for `component_foo`).
- `.aitask-scripts/brainstorm/templates/explorer.md` (lines ~41, ~83), `detailer.md`, `initializer.md`, `_section_format.md` — document that `prefix_*` globs are supported and expand to all matching node keys; replace invented `tradeoff_pros, tradeoff_cons` with `tradeoff_*` (or instruct "use the real dimension keys from your Dimension Keys block"). Templates are agent-run prompts, NOT skills — the Claude-Code-first skill-porting rule does not apply; no Codex/OpenCode mirror needed.
- `tests/test_brainstorm_sections.py` — add tests.

## Reference Files for Patterns
- `DIMENSION_PREFIXES` and `is_dimension_field()` in `.aitask-scripts/brainstorm/brainstorm_schemas.py:21,140`.
- `on_dimension_row_activated` (`brainstorm_app.py:5077-5102`) calls `get_sections_for_dimension(parsed, event.dim_key)` — it picks up the fix automatically once the helper expands globs; no change needed there beyond confirming behavior.
- Existing tests in `tests/test_brainstorm_sections.py` (unittest; run via `bash tests/run_all_python_tests.sh`).

## Implementation Plan
1. In `brainstorm_sections.py`, add a helper e.g. `_dimension_matches_tag(dim_key: str, tag: str) -> bool`: returns `dim_key == tag`, OR (if `tag.endswith("*")`) `dim_key.startswith(tag[:-1])`. Purely string-based.
2. Rewrite `get_sections_for_dimension(parsed, dimension)` to return sections where `any(_dimension_matches_tag(dimension, t) for t in sec.dimensions)`.
3. Extend `validate_sections(parsed, node_keys: list[str] | None = None)`: keep current checks; when `node_keys` is provided, for each non-glob tag (not ending in `*`) that is a dimension field but is not in `node_keys`, append an error like `Section '<name>' references unknown dimension key '<tag>'`. Glob tags and the no-`node_keys` case are unchanged (backward compatible).
4. In `brainstorm_app.py` `_render_node_detail_widgets`, replace the `section_counts[dim] += 1` loop: for each section, build the set of real keys it links — `{k for k in dims for t in sec.dimensions if _dimension_matches_tag(k, t)}` — then `for k in that_set: section_counts[k] = section_counts.get(k,0)+1`. Import the helper from brainstorm_sections.
5. Update the templates' dimension-tag guidance as above.
6. Tests: glob `component_*` resolves `component_foo` in `get_sections_for_dimension`; mixed exact+glob dedupes; `validate_sections` with `node_keys` flags an invented key but accepts a glob.

## Verification Steps
- `bash tests/run_all_python_tests.sh` (new + existing pass).
- Manual (no regeneration): `ait brainstorm` → open session 635 → focus a rich node (e.g. n004) → dimension rows previously `[0 §]` for glob-only-covered keys now show real counts; Enter on such a row opens the proposal (no "No sections tagged" warning). Confirm n005/n007/n008 stubs still legitimately show `[0 §]` (they have no markers at all).
- Template-side (optional, generation): run one `explore`/`detail` op and confirm the new proposal uses `tradeoff_*` / real keys, not invented `tradeoff_pros`.
