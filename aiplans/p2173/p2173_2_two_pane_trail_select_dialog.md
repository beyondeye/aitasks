---
Task: t2173_2_two_pane_trail_select_dialog.md
Parent Task: aitasks/t2173_trail_select_two_pane_dialog_and_discovery_cache.md
Sibling Tasks: aitasks/t2173/t2173_1_*.md
Archived Sibling Plans: aiplans/archived/p2173/p2173_*_*.md
Base branch: main
Output branch: main
---

# t2173_2 — Two-pane `TrailSelectScreen`

Child of t2173 (parent plan: `aiplans/p2173_trail_select_two_pane_dialog_and_discovery_cache.md`,
approved 2026-10-31 after a review round). The parent's Context section explains the
measured costs (~3.3s per scan, 13 trails) and why the dialog is hard to scan.

### Design

`board/board_trail_view.py` — replace `TrailSelectItem` + the list body of
`TrailSelectScreen` (:704–:820). Constructor signature, `GuardedModalScreen`
base, `TRAIL_SELECT_RESCAN`, `open_handles`, `allow_rescan` and dismissal
values unchanged.

```
Container#trail_select_dialog            (90% × 80%, own ids — not #dep_picker_dialog)
  Label#trail_select_title     "Select trail" (bold)
  Label#trail_select_hint      "Type to filter · ↑/↓ move · Enter open · Ctrl+R rescan · Esc cancel"
                               (the Ctrl+R segment only when allow_rescan)
  Horizontal#trail_select_body (1fr)
    Vertical#trail_select_left (40%, min-width 24)
      Input#trail_select_search   placeholder "Filter by title…"   (focused on mount, keeps focus)
      TrailTitleList#trail_select_list   OptionList subclass, can_focus=False; one Option per
                                         shown trail, id = handle, prompt = title [+ "  ● open"]
    TrailDetailPane#trail_select_detail (1fr)   VerticalScroll subclass, can_focus=False
      Static#trail_select_detail_body
  Horizontal#trail_select_buttons
    Button "Cancel" #btn_trail_select_cancel
```

- **Focus model (settled)**: the search `Input` and the Cancel button are the
  only focusable widgets. Both the list and the detail pane are
  `can_focus=False` subclasses — `VerticalScroll` is focusable by default in
  Textual 8.2.7, and a focused detail pane would re-activate both Apps'
  priority `nav_up/nav_down` (focus moves instead of scrolling). Tab /
  Shift+Tab cycle box ↔ Cancel; with Cancel focused, ↑/↓ follow each host's
  existing modal behaviour (back to the box). The detail pane scrolls with
  **PgUp/PgDn** (screen bindings; neither `Input` nor either App binds them)
  and the mouse wheel; ↑/↓ always belong to the list.
- **Keys**: screen `BINDINGS` `up`/`down` → the list's cursor actions,
  `pageup`/`pagedown` → the detail pane's `scroll_page_up/down`
  (non-priority: with the `Input` focused both Apps'
  priority `nav_up/down` are inactive — `KanbanApp.check_action` :2465,
  `TrailsApp.check_action` :784 — so arrows fall through to the screen);
  `Input.Submitted` → dismiss highlighted handle; `OptionList.OptionSelected`
  (click) → dismiss that handle; `escape` + Cancel → `None`;
  **`ctrl+r` → `TRAIL_SELECT_RESCAN` when `allow_rescan`** (decision: a typed
  `r` must reach the search box, and a focus-aware `r` would never fire because
  the box always has focus).
- **Hint**: two lines so it fits 80×24 —
  `Type to filter · ↑/↓ move · Enter open · Esc cancel` and
  `PgUp/PgDn scroll details` (+ ` · Ctrl+R rescan` when `allow_rescan`).
- **Filtering**: `fuzzy_filter.rank(query, infos, key=_trail_select_title)` —
  title only (`doc.title or info.name or info.handle`, factored out of the old
  row code); blank query = original order; highlight resets to the first match;
  no match → empty list and the detail pane says `No trail title matches "<q>"`;
  Enter with no match does nothing.
- **Detail pane** — pure `trail_select_detail(info, overlap_notes, is_open) ->
  Text` (headless-testable, all values appended as `Text`, never markup):
  title (+ `● open`), handle; Owner `t<id>` + `(archived)` / `(folded)`; Scope
  kind; Freshness `_trail_stored_freshness(info)`; Generated
  `trail_generated_label(raw) or raw or "?"`; a **Shared tasks** block from
  `compute_trail_overlaps` (`<ref> — also in <other title>`); for `load_error`
  trails an **Error** block and the recorded `versions` fallback. Re-rendered
  on `OptionList.OptionHighlighted` and after each filter change.
- **CSS**: own `DEFAULT_CSS` covering every rule above plus a visible
  highlight for the unfocused list
  (`#trail_select_list > .option-list--option-highlighted`), per
  tui_conventions "Modals pushed by multiple Apps".
- Remove `TrailSelectItem`; drop it from `aitask_board.py`'s re-export (:125)
  and the export lists in `tests/test_board_trail_view.py` (:63, :207).

### Steps

1. Implement the screen + `trail_select_detail` + `_trail_select_title` in
   `board_trail_view.py`; update the module docstring's modal list if needed.
2. Tests:
   - `tests/test_board_trail_view.py` `ModalDefaultCssTests`: `#trail_select_dialog`
     at 0.9 width, scoping negative control with a plain modal reusing that id.
   - `tests/test_board_bytrail_view.py` (:685–:810): highlight moves on `down`
     and changes the frame while the search box keeps focus; overlap note shows
     in the detail pane and not in the list; last option reachable (scrolled
     into view), Cancel visible; hint not truncated at 80×24.
   - New, in **both** hosts (KanbanApp By-Trail and TrailsApp): typing filters
     by title only (a query matching only an owner/scope string matches
     nothing); subsequence match; ↑/↓ move the highlight and update the detail
     pane; Enter opens the highlighted trail; click opens; Esc → nothing opened;
     typed `r` lands in the box and does not rescan; Ctrl+R rescans only with
     `allow_rescan`; `● open` marker in list and detail; error trail shows error
     + versions.
   - **Focus cycle + overflowed details, in both hosts**: with a detail pane that
     overflows (an error trail with many recorded versions, or many shared
     tasks) — Tab and Shift+Tab from the box visit only the box and Cancel, never
     `#trail_select_detail` or the list (`app.focused` after each press); PgDn
     raises the pane's `scroll_y` and PgUp lowers it; the last detail line is
     viewable after enough PgDn; ↑/↓ still move the list highlight after a Tab
     round-trip; with Cancel focused, ↑ returns focus to the box rather than
     scrolling or leaving the dialog.
   - `tests/test_trails_app.py`: `pilot.press("r")` in the selector → `ctrl+r`
     (:203, :1611; check :2137 is the main-screen `r`); :1367 query the list's
     options instead of `TrailSelectItem`; `test_a_stale_selector_key_pops_nothing`
     unchanged (it calls `action_rescan`/`action_cancel`).
   - `tests/test_board_detail_followup_kind.py:539` — check whether it targets
     this dialog's `#btn_dep_cancel`; adapt if so.
   - `tests/perf/trails_pilot_bench.py`: select the trail by typing/highlight,
     not by focusing a `TrailSelectItem`.
3. Docs: `tuis/trails/reference.md` "In the trail selector" table (type to
   filter, ↑/↓, Enter or click, Ctrl+R, Esc) and a sentence on the two panes;
   every "`r` in the selector" in `how-to.md`, `_index.md`, `reference.md`,
   `workflows/implementation-trails.md` → Ctrl+R; `how-to.md` "Rows for trails
   that are already open are marked `● open`" still true (keep). Run
   `check_links.py --build`.
4. Step 8e: `./ait note 1647_5 --from 2173_2` — `TrailSelectItem` is gone; model
   `TrailMergeSelectScreen` on the two-pane `TrailSelectScreen` (search box +
   `TrailTitleList` + `trail_select_detail`), overlaps now render in the detail
   pane. Hedge: the note's SHA dates it.

## Verification

- `bash tests/run_all_python_tests.sh` — last line `PYTHON SUITE: PASSED`.
- Manual, both TUIs, 80×24 and a wide terminal: type to filter, ↑/↓, Enter, click, PgUp/PgDn on a long detail pane, Tab cycle (box ↔ Cancel), Ctrl+R (`ait trails` only), Esc, an error trail's detail pane.
- `cd website && python3 check_links.py --build`.
- Step 8e note to t1647_5; Step 9 archives this child and then the parent t2173 (last child).

## Risk

### Code-health risk: low
- The dialog rewrite changes keyboard routing in two Apps that bind arrows with `priority=True`; a host whose `check_action` does not fall through for the focused `Input` would lose ↑/↓, and a focusable detail pane would re-activate the priority arrows · severity: low · → mitigation: none (both-host key + focus-cycle tests in step 2)
- ~6 test files and the perf bench need migration with the dialog · severity: low · → mitigation: none

### Goal-achievement risk: low
None identified.
