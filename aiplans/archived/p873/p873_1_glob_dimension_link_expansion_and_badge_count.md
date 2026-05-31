---
Task: t873_1_glob_dimension_link_expansion_and_badge_count.md
Parent Task: aitasks/t873_fix_brainstorm_dimension_proposal_linking_and_compare.md
Sibling Tasks: aitasks/t873/t873_*.md
Archived Sibling Plans: aiplans/archived/p873/p873_*_*.md
Worktree: aiwork/t873_1_glob_dimension_link_expansion_and_badge_count
Branch: aitask/t873_1_glob_dimension_link_expansion_and_badge_count
Base branch: main
plan_verified:
  - claudecode/opus4_8 @ 2026-05-31 13:52
---

# Plan: t873_1 — Glob/prefix dimension-link expansion + badge-count fix + template tag hygiene

Foundational child of t873 (runs first). Makes glob section tags
(`[dimensions: component_*]`) actually resolve to real node dimension keys, fixes
the `[N §]` badge to count real keys, and stops the agent templates from emitting
unexpandable globs / invented tag keys.

## Root cause
`get_sections_for_dimension()` (`.aitask-scripts/brainstorm/brainstorm_sections.py:170-174`)
tests `dimension in sec.dimensions` — exact membership — so a glob tag
`component_*` never matches `component_foo`. The detail-pane badge loop
(`brainstorm_app.py:5024-5026`) increments `section_counts[dim]` keyed by the
literal tag string, counting `"component_*"` instead of the real keys. The
explorer/detailer/initializer templates literally instruct agents to emit
`[dimensions: component_*]` and invented `tradeoff_pros, tradeoff_cons`.

## Steps
1. **`brainstorm_sections.py` — match predicate.** Add:
   ```python
   def _dimension_matches_tag(dim_key: str, tag: str) -> bool:
       if tag.endswith("*"):
           return dim_key.startswith(tag[:-1])
       return dim_key == tag
   ```
   (Module-private; pure string logic.)
2. **`get_sections_for_dimension`** → return
   `[sec for sec in parsed.sections if any(_dimension_matches_tag(dimension, t) for t in sec.dimensions)]`.
3. **`validate_sections(parsed, node_keys=None)`** — keep existing checks. When
   `node_keys` is given, for each section tag that is a dimension field, is NOT a
   glob (`not tag.endswith("*")`), and `tag not in node_keys`, append
   `f"Section '{sec.name}' references unknown dimension key '{tag}'"`. Backward
   compatible (no `node_keys` ⇒ unchanged).
4. **`brainstorm_app.py:5017-5039`** — rewrite the count loop in
   `_render_node_detail_widgets`. `dims = get_dimension_fields(node_data)` is
   already in scope. Import `_dimension_matches_tag` (or a small public wrapper).
   For each parsed section, compute the set of real keys it links and count each
   once:
   ```python
   for sec in parsed_proposal.sections:
       linked = {k for k in dims for t in sec.dimensions
                 if _dimension_matches_tag(k, t)}
       for k in linked:
           section_counts[k] = section_counts.get(k, 0) + 1
   ```
   `on_dimension_row_activated` (:5090) needs no change — it calls
   `get_sections_for_dimension`, which now expands globs.
5. **Templates** — `templates/explorer.md` (~L41 list, ~L83 tradeoffs section),
   `detailer.md`, `initializer.md`, `_section_format.md`: state that `prefix_*`
   globs are supported and expand to all matching node keys; replace invented
   `tradeoff_pros, tradeoff_cons` with `tradeoff_*` (or "reference real keys from
   your Dimension Keys block"). Agent prompts, not skills — no Codex/OpenCode
   mirror.
6. **Tests** (`tests/test_brainstorm_sections.py`): glob `component_*` resolves
   `component_foo`; exact+glob on one section dedupes to a single count;
   `validate_sections(parsed, node_keys=[...])` flags an invented non-glob tag but
   accepts a glob and accepts a real key.

## Verification
- `bash tests/run_all_python_tests.sh`.
- Manual (no regeneration): `ait brainstorm` → session `crew-brainstorm-635` →
  rich node (n004) → glob-only-covered dimension rows now show real `[N §]` and
  Enter opens the proposal; stub nodes n005/n007/n008 still show `[0 §]`
  legitimately (zero markers).
- See parent `aiplans/p873_*.md` Verification for the no-regeneration rationale.

## Post-implementation
Follow task-workflow Step 8 (review/commit) and Step 9 (archival/merge). Record
any related upstream defect in the plan's Final Implementation Notes.

## Final Implementation Notes
- **Actual work done:** Added `dimension_matches_tag(dim_key, tag)` to
  `brainstorm_sections.py` (exact match or `prefix_*` glob). `get_sections_for_dimension`
  now expands globs so glob-only-linked dimensions resolve. `validate_sections`
  gained an optional `node_keys` arg that flags invented (non-glob) tags absent
  from the node's real keys, while always accepting globs. The detail-pane
  `section_counts` loop in `brainstorm_app.py:_render_node_detail_widgets` now
  expands each section's tags against the node's real keys (`dims`) and counts
  each section once per real key. Templates: `explorer.md` tradeoffs section uses
  `tradeoff_*` (was invented `tradeoff_pros, tradeoff_cons`) in both the field
  list and the section tag; `_section_format.md` documents glob support and
  warns against inventing keys (propagates to detailer/synthesizer/initializer
  via their `<!-- include: _section_format.md -->`). Added 8 unit tests.
- **Deviations from plan:** (1) Named the predicate `dimension_matches_tag`
  (public) rather than the plan's `_dimension_matches_tag` — `brainstorm_app.py`
  imports it cross-module, so a public name is cleaner than importing an
  underscore-prefixed symbol. (2) Only `explorer.md` + the shared
  `_section_format.md` needed editing; `detailer.md`/`initializer.md` already use
  `component_*`/`assumption_*`/`tradeoff_*` globs consistently and inherit the
  glob clarification through the include, so no separate edits there.
- **Issues encountered:** The full `tests/run_all_python_tests.sh` run reported 2
  failures, both pre-existing and unrelated to this task: `test_shortcut_scopes`
  (`board.agent_cmd` not registered) from in-flight shortcut-scopes work present
  in the working tree (`lib/shortcut_scopes.py`, `keybinding_registry.py`,
  `agent_command_screen.py`, `settings_app.py`), and `test_desync_state`
  (`python_resolve.sh: No such file or directory` in the fake-repo scaffold).
  Neither touches brainstorm; the brainstorm trio (`test_brainstorm_sections`,
  `test_brainstorm_wizard_sections`, `test_section_viewer_filter` — 49 tests) is
  green.
- **Key decisions:** Glob matching is purely string-based (no node data); only
  the count loop and the opt-in `node_keys` validation use real keys. The count
  loop dedupes per (section, real_key) via a set comprehension so a section
  tagging both `component_*` and `component_foo` is counted once. `node_keys`
  validation is opt-in to keep `validate_sections(parsed)` backward compatible.
- **Upstream defects identified:** None. This task's symptom (glob tags not
  resolving) was self-contained in `get_sections_for_dimension` / the count loop;
  no separate pre-existing bug seeded it. The two unrelated suite failures noted
  above stem from active in-flight work in the working tree and a scaffold/env
  condition, not committed defects to file against.
- **Notes for sibling tasks:**
  - **t873_2 (scroll):** Confirmed live by the user — opening a proposal via a
    dimension row does NOT land on the matching section; it stays at the top.
    Auto-scroll path: `SectionViewerScreen.on_mount` queues
    `_pending_auto_scroll = filtered[0].name` → `_poll_auto_scroll` →
    `SectionAwareMarkdown.scroll_to_section` (`lib/section_viewer.py:367-409`,
    `277-289`); the minimap jump (`on_section_minimap_section_selected` :420)
    shares the same `scroll_to_section`. t873_1 now opens the viewer for
    glob-linked dims too, so t873_2's fix benefits more cases.
  - **t873_4 (compare):** `dimension_matches_tag` is reusable if glob-aware
    matching is needed, though compare scoping is by real node keys.
  - Detail-pane dimension keys come from `get_dimension_fields(node_data)`;
    badge counts now reflect real keys.
