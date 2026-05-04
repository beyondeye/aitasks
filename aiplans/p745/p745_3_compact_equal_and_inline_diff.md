---
Task: t745_3_compact_equal_and_inline_diff.md
Parent Task: aitasks/t745_improve_node_comparator.md
Sibling Tasks: aitasks/t745/t745_4_diffviewer_screen_integration.md, aitasks/t745/t745_5_manual_verification_improve_node_comparator.md
Archived Sibling Plans: aiplans/archived/p745/p745_1_context_aware_footer.md, aiplans/archived/p745/p745_2_compare_regenerate_shortcut.md
Base branch: main
plan_verified:
  - claudecode/opus4_7_1m @ 2026-05-05 00:15
---

# Plan — t745_3: Compact equal-value rows + inline word-level diff in brainstorm Compare

## Context

In the brainstorm TUI's Compare tab, two design proposals are listed side-by-side as a DataTable of dimension key → value rows. Two issues from parent t745:

3. **Redundant equal-value rows.** When both nodes share the same value for a dimension, the value is printed in full in both columns instead of being collapsed.
4. **No "what changed" highlighting.** When values differ, the raw text is printed without any indication of which words changed.

This task addresses both by reusing the diffviewer's existing `_word_diff_texts` helper. The fix promotes that helper to a public `word_diff_texts` API, re-exports it from `diffviewer/__init__.py`, and rewrites `brainstorm_app._build_compare_matrix` to render compact equal rows and inline word-level diffs for differing 2-node rows.

User-confirmed during prior planning:
- Equal dims → render value once in node 1's cell, render `← same` (dim green) in node 2's cell. DataTable does not support real cell-spanning.
- Differing dims (2-node) → inline word-level diff using `TAG_STYLES["replace"]` for changed words and `TAG_STYLES["replace_dim"]` for matching ones.
- 3+ node comparisons keep the existing similarity-color row behavior.

## Verification of existing plan against current codebase

Source plan: `aiplans/p745/p745_3_compact_equal_and_inline_diff.md`

| Plan reference | Verified |
|---|---|
| `diff_display.py:118` — `_word_diff_texts` location | ✅ unchanged |
| `diff_display.py:21-31` — `TAG_STYLES` with `replace`, `replace_dim` | ✅ unchanged |
| `diff_display.py:450,456,516` — internal callers of `_word_diff_texts` | ✅ confirmed; back-compat alias keeps them working |
| `diffviewer/__init__.py` — exists, empty (0 bytes) | ✅ confirmed |
| `brainstorm_app.py:2898-2916` — row-build loop | ⚠️ shifted (post t745_1/t745_2). **Actual location: `_build_compare_matrix` at 2971-3024, row-loop at 3001-3018.** |
| `brainstorm_app.py` imports — `Text`, `SequenceMatcher` already present | ✅ confirmed (lines 39, 8) |
| sys.path includes `.aitask-scripts/` | ✅ confirmed (lines 12-13 of brainstorm_app.py) |

The structural approach and code snippets in the source plan are correct. Only line numbers in the brainstorm_app.py reference need updating; the implementation snippets are unaffected.

## Critical files

- `.aitask-scripts/diffviewer/diff_display.py` (line 118) — promote `_word_diff_texts` → `word_diff_texts`, add back-compat alias.
- `.aitask-scripts/diffviewer/__init__.py` (currently empty) — re-export `word_diff_texts` and `TAG_STYLES`.
- `.aitask-scripts/brainstorm/brainstorm_app.py` (lines 3001-3018, the row-building loop in `_build_compare_matrix`) — branch on equal-vs-differing and on 2-node-vs-3+-node case.

## Reference

- `.aitask-scripts/diffviewer/diff_display.py:21-31` — `TAG_STYLES` dict (`replace`, `replace_dim`, `equal`, etc.).
- `.aitask-scripts/diffviewer/diff_display.py:118-162` — current helper signature and word-tokenization logic.
- `.aitask-scripts/diffviewer/diff_display.py:516-520` — existing call shape using `replace` + `replace_dim` styles for both sides (mirrors the use-case for the brainstorm Compare table).

## Implementation steps

1. **Promote helper.** In `diff_display.py`:
   - Rename `_word_diff_texts` → `word_diff_texts` (line 118).
   - Immediately after the function definition, add the back-compat alias:
     ```python
     _word_diff_texts = word_diff_texts  # back-compat alias for internal callers
     ```
   - Existing internal callers at lines 450, 456, 516 keep working without further edits.

2. **Re-export.** Replace the empty `.aitask-scripts/diffviewer/__init__.py` with:
   ```python
   from .diff_display import word_diff_texts, TAG_STYLES

   __all__ = ["word_diff_texts", "TAG_STYLES"]
   ```

3. **Rewrite the row-build loop in `_build_compare_matrix`.** Add the import at the top of `brainstorm_app.py` (after the existing `from rich.text import Text` line, alongside the existing imports):
   ```python
   from diffviewer.diff_display import word_diff_texts, TAG_STYLES
   ```
   Then replace the existing loop (current lines 3001-3018) with:
   ```python
   # Add dimension rows with color-coded values
   for key in all_keys:
       raw_values = [str(node_dims[nid].get(key, "—")) for nid in selected_nodes]
       unique = set(raw_values)
       n = len(selected_nodes)

       if len(unique) == 1:
           # Equal values: collapse into a single visible value
           if n == 2:
               styled = [
                   Text(raw_values[0], style="green"),
                   Text("← same", style="dim green"),
               ]
           else:
               styled = [Text(v, style="green") for v in raw_values]
           table.add_row(key, *styled, key=key)
           continue

       # Differing values
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
   The `←` is the "←" arrow character.

4. **Verify `_add_similarity_row` (lines 3026-3049) still works.** It only depends on `nodes`, `node_dims`, `all_keys` — none of which are touched by the loop rewrite. The avg-similarity row still appends as before.

## Verification

1. Launch `./.aitask-scripts/aitask_brainstorm_tui.sh 635`. Switch to the **Compare** tab; pick `n000` and `n001`.
   - **Equal dims**: value rendered once in green in node 1's cell; node 2's cell shows `← same` in dim green.
   - **Differing dims**: word-level highlights inside both cells. Common words use `replace_dim` (dim brown background); differing words use `replace` (full brown background). The visual style matches the diffviewer's word-level diff for replace rows.
   - **Avg similarity row** at the bottom still renders.

2. Sanity-check the diffviewer TUI to ensure the renamed helper hasn't broken the existing usages:
   - `./.aitask-scripts/aitask_diffviewer.sh` (open any plan pair) — confirm side-by-side word-level diff still highlights replace rows correctly.

3. Run any existing tests that touch these modules:
   ```bash
   ls tests/test_brainstorm_*.sh tests/test_diffviewer_*.sh 2>/dev/null
   # Run whatever exists; skip if none.
   ```

## Out of scope (note in Final Implementation Notes)

- 3+ node comparisons keep the current row-color behavior; inline word-diff is 2-node only.
- Structural-mode diff for very long values.
- Pagination/truncation of long values inside DataTable cells.

## Notes for sibling tasks

- The `word_diff_texts` public helper is now reusable across the codebase. Future TUIs that need inline word-diff (e.g., t745_4 diffviewer screen integration) can `from diffviewer import word_diff_texts, TAG_STYLES` directly.
- Line numbers in the brainstorm `_build_compare_matrix` will shift again after this change. Sibling tasks (t745_4, t745_5) should re-locate the function by name, not by line.
