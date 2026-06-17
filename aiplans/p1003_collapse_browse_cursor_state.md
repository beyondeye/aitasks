---
Task: t1003_collapse_browse_cursor_state.md
Worktree: (none — current branch, profile 'fast')
Branch: main
Base branch: main
---

# t1003 — Collapse browse cursor state

## Context

t983_3 wired the new `NodeSelection` model into the brainstorm Browse UI but
left the **legacy `_current_focused_node_id` field running in parallel** with
`self._selection.primary`. Both are kept in sync by hand at every write site.
This dual cursor state is documented debt (code-health medium, risk-mitigation
`collapse_browse_cursor_state`): a future edit that updates one but not the
other silently drifts the cursor. This task retires the legacy field so there is
**one cursor source of truth** — `self._selection.primary`.

Every existing write site **already** calls the paired `self._selection`
method right next to the legacy write, and every legacy read maps 1:1 onto
`self._selection.primary`. So the collapse is mechanical: delete the legacy
writes (the `_selection` call beside each already does the work), repoint the
reads, drop the field, and refresh the docs/tests.

All code lives in `.aitask-scripts/brainstorm/brainstorm_app.py`. The
`NodeSelection` model (`set_primary` / `remove` / `primary` / `effective` /
`cardinality`) is at lines 2231–2299 and is unchanged.

## Changes

### 1. `.aitask-scripts/brainstorm/brainstorm_app.py`

**Remove the field + its dual-state comment (lines 5621–5627):**
- Delete `self._current_focused_node_id: str | None = None` (5621).
- Rewrite the `self._selection = NodeSelection()` comment (5622–5626): drop the
  "Runs alongside the legacy `_current_focused_node_id` cursor (kept in sync …)
  dual cursor state is documented debt" wording. New comment states the
  selection model is now the **sole** Browse cursor; `space` toggles marks.

**Repoint the 6 read sites → `self._selection.primary`:**
| Line | Method | Change |
|------|--------|--------|
| 5652 | `check_action` | `if not self._current_focused_node_id:` → `if not self._selection.primary:` |
| 6238 | `action_node_action` | `node_id = self._current_focused_node_id` → `... = self._selection.primary` |
| 6306 | `action_toggle_deferred` | `node_id = self._current_focused_node_id` → `... = self._selection.primary` |
| 6531 | `_browse_toggle_pane_focus` | `if self._current_focused_node_id:` → `if self._selection.primary:` |
| 6533 | `_browse_toggle_pane_focus` | `if r.node_id == self._current_focused_node_id:` → `... == self._selection.primary:` |
| 7949 | `on_dimension_row_activated` | `node_id = self._current_focused_node_id` → `... = self._selection.primary` |

**Delete the 5 redundant legacy write sites** (the adjacent `_selection` call
already covers each):
- 6256 `_open_operations_dialog`: delete `self._current_focused_node_id = node_id`
  — line 6257 `self._selection.set_primary(node_id)` remains (trim the anchor
  comment's stale dual-write framing if needed).
- 6274 `_open_operations_dialog` (node-deleted branch): delete
  `self._current_focused_node_id = None` — line 6275 `self._selection.remove(node_id)`
  remains (clears primary if it was the cursor).
- 6460–6461 `_on_delete_node_result`: delete the
  `if self._current_focused_node_id in deleted: self._current_focused_node_id = None`
  block — the existing `for nid in deleted: self._selection.remove(nid)` loop
  (6464–6465) already clears the primary when the cursor node is deleted, via
  `NodeSelection.remove`. Update the adjacent comment (6462–6463) to drop the
  "Keep the … model coherent" dual-state framing — it's now the only path.
- 7930 `_show_browse_node_detail`: delete `self._current_focused_node_id = node_id`
  — line 7931 `self._selection.set_primary(node_id)` remains. Rewrite the
  docstring (7919–7929): remove "keeps the legacy `_current_focused_node_id`
  cursor … in sync until the dual cursor state is collapsed"; state it now sets
  the single `NodeSelection.primary` cursor.
- 7936 `_show_brief_in_detail`: delete `self._current_focused_node_id = None` —
  line 7937 `self._selection.set_primary(None)` remains.

**Stale historical comment (line 2226):** soften the NodeSelection header comment
("the legacy single-selection `_current_focused_node_id` path is untouched until
t983_3 wires this model in") so it doesn't reference a field that no longer
exists — note the model is now the sole cursor (t1003).

After these edits, `grep -n _current_focused_node_id brainstorm_app.py` must
return **zero** matches.

### 2. Tests — migrate the 5 references onto the selection model

- `tests/test_brainstorm_node_hub.py:276` (`_bare_app`): delete
  `app._current_focused_node_id = None` — `app._selection = NodeSelection()`
  (line 275) already starts with `primary=None`.
- `tests/test_brainstorm_node_hub.py:360`: delete
  `self.assertEqual(app._current_focused_node_id, "n001_test")` — line 359
  already asserts `app._selection.primary == "n001_test"` (the cursor-anchor
  invariant), now the sole assertion.
- `tests/test_brainstorm_node_delete.py:204`: `app._current_focused_node_id = "n002_c"`
  → `app._selection.set_primary("n002_c")` (seed the cursor via the model).
- `tests/test_brainstorm_node_delete.py:215`:
  `self.assertIsNone(app._current_focused_node_id)` →
  `self.assertIsNone(app._selection.primary)`. This becomes the **consolidated-cursor
  regression test**: it now proves the delete cascade clears the primary cursor
  purely through `NodeSelection.remove` in the `for nid in deleted` loop (the
  legacy line is gone), which is exactly the contract this task collapses onto.
- `tests/test_brainstorm_node_detail_panel.py:288`:
  `self.assertIsNone(app._current_focused_node_id)` →
  `self.assertIsNone(app._selection.primary)` (Task-Brief toggle clears the cursor).

No new test file is needed — the existing delete/detail/hub tests, repointed,
cover the consolidated cursor's set, read, and delete-cleanup paths.

## Verification

1. `grep -n "_current_focused_node_id" .aitask-scripts/brainstorm/brainstorm_app.py tests/` → **no matches**.
2. Run the brainstorm test suite (Browse selection / delete / detail / hub):
   ```bash
   for t in node_selection node_delete node_detail_panel node_hub \
            node_action_integration node_action_modal node_action_relevance; do
     python3 tests/test_brainstorm_$t.py || echo "FAIL: $t"
   done
   ```
   All must pass. `node_delete` and `node_detail_panel` exercise the
   consolidated cursor-clear path; `node_hub` exercises the open-dialog anchor.
3. Sanity-compile: `python3 -c "import ast; ast.parse(open('.aitask-scripts/brainstorm/brainstorm_app.py').read())"`.

## Step 9 (Post-Implementation)

Single task, current branch (profile 'fast', no worktree/merge). After review +
commit, archival proceeds via `aitask_archive.sh 1003`.

## Risk

### Code-health risk: low
- Mechanical debt-reduction confined to one source file + three test files; every
  removed legacy write has a pre-existing paired `self._selection` call and every
  read maps 1:1 to `.primary`, so the collapse removes an implicit contract rather
  than adding one · severity: low · → mitigation: none (this task *is* the t983_3 mitigation)
- The one non-trivial site is the delete-cascade cursor-clear (6460–6461), which
  now relies solely on the `NodeSelection.remove` loop; verified the loop already
  clears `primary` when the cursor node is deleted, and the repointed
  `test_brainstorm_node_delete` asserts exactly this · severity: low · → mitigation: covered by adjusted test

### Goal-achievement risk: low
- The goal (single cursor source of truth, field retired) is concrete and fully
  covered by the enumerated edits; the zero-grep check is an objective completion
  gate · severity: low · → mitigation: none
