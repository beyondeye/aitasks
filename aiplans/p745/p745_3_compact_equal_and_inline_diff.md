---
Task: t745_3_compact_equal_and_inline_diff.md
Parent Task: aitasks/t745_improve_node_comparator.md
Sibling Tasks: aitasks/t745/t745_1_context_aware_footer.md, aitasks/t745/t745_2_compare_regenerate_shortcut.md, aitasks/t745/t745_4_diffviewer_screen_integration.md
Archived Sibling Plans: aiplans/archived/p745/p745_*_*.md
Worktree: aiwork/t745_3_compact_equal_and_inline_diff
Branch: aitask/t745_3_compact_equal_and_inline_diff
Base branch: main
---

# Plan — t745_3: Compact equal-value rows + inline word-level diff

## Context

Issues 3 and 4 from the parent: equal-valued dimensions are printed redundantly, and differing values are dumped raw without highlighting WHAT changed. This task makes equal rows compact (single shared cell pattern) and renders inline word-level diffs for differing rows by reusing diffviewer's `_word_diff_texts` helper, promoted to public API.

User-confirmed:
- Equal dims → render value once, `← same` marker in second cell (DataTable can't span).
- Differing → inline word-level diff per cell using the diff_engine helper.

## Critical files

- `.aitask-scripts/diffviewer/diff_display.py:118` — promote `_word_diff_texts` to `word_diff_texts`.
- `.aitask-scripts/diffviewer/__init__.py` — create if absent; re-export the helper.
- `.aitask-scripts/brainstorm/brainstorm_app.py:2898-2916` — branch on equal vs differing and on 2-node vs 3+-node case.

## Reference

- `.aitask-scripts/diffviewer/diff_display.py:21-31` — `TAG_STYLES` dict with `replace`, `replace_dim`.
- `.aitask-scripts/diffviewer/diff_display.py:118-162` — current helper signature and word-tokenization logic.

## Implementation steps

1. **Promote helper.** In `diff_display.py`, rename `_word_diff_texts` → `word_diff_texts`. After the function definition, add:
   ```python
   _word_diff_texts = word_diff_texts  # back-compat alias
   ```
   (Existing internal callers at lines 450, 456, 516 keep working; no need to edit them.)

2. **Re-export.** Create `.aitask-scripts/diffviewer/__init__.py` if absent, with:
   ```python
   from .diff_display import word_diff_texts, TAG_STYLES
   ```
   If the file already exists, append the import.

3. **Modify `_build_compare_matrix`.** Replace lines 2898–2916 with:
   ```python
   from diffviewer.diff_display import word_diff_texts, TAG_STYLES

   for key in all_keys:
       raw_values = [str(node_dims[nid].get(key, "—")) for nid in selected_nodes]
       unique = set(raw_values)
       n = len(selected_nodes)

       if len(unique) == 1:
           if n == 2:
               styled = [
                   Text(raw_values[0], style="green"),
                   Text("← same",       style="dim green"),
               ]
           else:
               styled = [Text(v, style="green") for v in raw_values]
           table.add_row(key, *styled, key=key)
           continue

       if n == 2:
           v1, v2 = raw_values
           t1, t2 = word_diff_texts(
               v1, v2,
               TAG_STYLES["replace"], TAG_STYLES["replace"],
               TAG_STYLES["replace_dim"], TAG_STYLES["replace_dim"],
           )
           table.add_row(key, t1, t2, key=key)
       else:
           max_sim = 0.0
           for i, x in enumerate(raw_values):
               for y in raw_values[i + 1:]:
                   sim = SequenceMatcher(None, x, y).ratio()
                   if sim > max_sim:
                       max_sim = sim
           color = "yellow" if max_sim > 0.6 else "red"
           styled = [Text(v, style=color) for v in raw_values]
           table.add_row(key, *styled, key=key)
   ```
   Hoist the `from diffviewer...` import to module top if Python style there favors it (most TUI imports in this file are at the top).

4. **Verify import path.** Launch the brainstorm TUI and ensure the import works. If it fails, fix the launcher (`.aitask-scripts/aitask_brainstorm.sh`) to add `.aitask-scripts/` to `PYTHONPATH` or `sys.path`. Reuse whatever pattern the diffviewer launcher already uses.

5. **Verify `_add_similarity_row`** still appends correctly — it should, since the new rows use the same `add_row(key, *cells)` call shape.

## Verification

- Launch `./.aitask-scripts/aitask_brainstorm.sh 635`. Switch to Compare; pick `n000` and `n001`.
- Equal dimensions show value once (green) and `← same` (dim green) in the second cell.
- Differing dimensions show colored word-level highlights inside both cells. Words common to both values are dimmed; the differing words use the `replace` background.
- Similarity row at the bottom still renders.
- Run `./.aitask-scripts/aitask_diffviewer.sh` briefly to confirm the renamed helper hasn't broken the diffviewer TUI itself.
- Run any existing tests: `bash tests/test_brainstorm_*.sh` (skip if absent).

## Out of scope (note in Final Implementation Notes)

- 3+ node comparisons keep current row-color behavior; inline word-diff is 2-node only.
- Structural-mode diff for very long values.
- Pagination/truncation of long values inside DataTable cells.

## Final Implementation Notes

(to be filled in at Step 8)
