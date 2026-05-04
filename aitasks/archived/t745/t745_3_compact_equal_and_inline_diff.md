---
priority: high
effort: medium
depends: [t745_1]
issue_type: enhancement
status: Done
labels: [ait_brainstorm]
assigned_to: dario-e@beyond-eye.com
implemented_with: claudecode/opus4_7_1m
created_at: 2026-05-04 22:21
updated_at: 2026-05-05 00:53
completed_at: 2026-05-05 00:53
---

## Context

Sibling of t745. Addresses parent issues 3 and 4: (3) the comparison table redundantly prints full values for dimensions where both nodes match; (4) when values differ, the raw text is dumped without highlighting WHAT changed. This task makes equal-valued rows compact and renders inline word-level diffs for differing rows by reusing the diffviewer's existing `_word_diff_texts` helper.

User-confirmed design decisions:
- Equal dims: render the value once, with a `← same` marker in the second node's cell (DataTable does not support real cell-spanning).
- Differing values: inline word-level diff per cell using diffviewer's `word_diff_texts` (promoted from underscore-prefixed `_word_diff_texts`).

This task is INDEPENDENT of t745_2 and t745_4 — depends only on t745_1.

## Dependency

Requires t745_1 (no functional dependency, but ordering keeps the codebase coherent and avoids merge conflicts in `BrainstormApp` BINDINGS area).

## Key Files to Modify

- `.aitask-scripts/diffviewer/diff_display.py`
  - Promote `_word_diff_texts` (line 118) → public `word_diff_texts`. Keep `_word_diff_texts = word_diff_texts` as an in-module alias for back-compat (existing internal callers at lines 450, 456, 516 keep working without edits — but updating them to the public name is fine).
- `.aitask-scripts/diffviewer/__init__.py` — create if absent; re-export `word_diff_texts` and `TAG_STYLES` so callers can `from diffviewer.diff_display import word_diff_texts`.
- `.aitask-scripts/brainstorm/brainstorm_app.py`
  - `_build_compare_matrix()` (lines 2898–2916) — branch on `len(unique) == 1` and on the 2-node-vs-3+-node case.

## Reference Files for Patterns

- `.aitask-scripts/diffviewer/diff_display.py:118-162` — current `_word_diff_texts` implementation; takes two strings and returns `(Text, Text)`.
- `.aitask-scripts/diffviewer/diff_display.py:21-31` — `TAG_STYLES` dict with `replace`, `replace_dim`, etc.
- `.aitask-scripts/brainstorm/brainstorm_app.py:2898-2916` — current row-building logic with similarity scoring.

## Implementation Plan

1. **Promote helper**: in `diff_display.py`, rename `_word_diff_texts` → `word_diff_texts`. Add a one-line `_word_diff_texts = word_diff_texts` alias to preserve internal callers without touching them. Re-export from `diffviewer/__init__.py`:
   ```python
   from .diff_display import word_diff_texts, TAG_STYLES
   ```
2. **Modify `_build_compare_matrix`** for the 2-node case:
   ```python
   raw_values = [str(node_dims[nid].get(key, "—")) for nid in selected_nodes]
   unique = set(raw_values)
   n = len(selected_nodes)

   if len(unique) == 1:
       # Equal values: render value once, "← same" in the second cell
       if n == 2:
           styled = [Text(raw_values[0], style="green"),
                     Text("← same", style="dim green")]
       else:
           # 3+ nodes: keep current full-value rendering with green
           styled = [Text(v, style="green") for v in raw_values]
       table.add_row(key, *styled, key=key)
       continue

   # Differing values
   if n == 2:
       from diffviewer.diff_display import word_diff_texts, TAG_STYLES
       v1, v2 = raw_values
       t1, t2 = word_diff_texts(
           v1, v2,
           TAG_STYLES["replace"], TAG_STYLES["replace"],
           TAG_STYLES["replace_dim"], TAG_STYLES["replace_dim"],
       )
       table.add_row(key, t1, t2, key=key)
   else:
       # 3+ nodes: keep current similarity-color row behavior
       max_sim = 0.0
       for i, v1 in enumerate(raw_values):
           for v2 in raw_values[i + 1:]:
               sim = SequenceMatcher(None, v1, v2).ratio()
               if sim > max_sim:
                   max_sim = sim
       color = "yellow" if max_sim > 0.6 else "red"
       styled = [Text(v, style=color) for v in raw_values]
       table.add_row(key, *styled, key=key)
   ```
3. Verify `_add_similarity_row()` (line 2924+) still appends correctly — it should, since DataTable just receives more `Text` rows.
4. Verify import path: `brainstorm_app.py` runs from `.aitask-scripts/brainstorm/`; `diffviewer/` is a sibling. The aitask_brainstorm.sh launcher inserts `.aitask-scripts/` (or its brainstorm subdir) into `sys.path` — confirm `from diffviewer.diff_display import ...` works at runtime. If it does not, fix in this task by adding the parent dir to sys.path in the launcher (preferred) or by using `sys.path` manipulation at the top of `brainstorm_app.py`.

## Verification Steps

- Launch `./.aitask-scripts/aitask_brainstorm.sh 635`. Switch to Compare tab; pick `n000` and `n001` (the two nodes that exist in the brainstorm-635 fixture).
- Equal-value dimensions show the value in the first node's column and `← same` (dim green) in the second.
- Differing-value dimensions show colored word-level diff highlights inside each cell — words that match between values are dimmed, words that differ are shown with the `replace` background style.
- The similarity score row at the bottom of the table still renders correctly.
- Run `bash tests/test_brainstorm_*.sh` if such tests exist.
- Optionally exercise the diffviewer TUI directly to confirm the renamed helper still works there: `./.aitask-scripts/aitask_diffviewer.sh` (open any plan pair).

## Out of scope (note in Final Implementation Notes)

- 3+ node comparisons (the inline word-diff is 2-node only; 3+ keeps current row coloring).
- Structural-mode diff for very long values (>1k chars).
- Pagination of long values inside DataTable cells.

## Notes for sibling tasks

- The `word_diff_texts` public helper is now reusable elsewhere in the codebase. Future TUIs that need inline word-diff can import it from `diffviewer.diff_display`.
