---
Task: t2173_2_two_pane_trail_select_dialog.md
Parent Task: aitasks/t2173_trail_select_two_pane_dialog_and_discovery_cache.md
Sibling Tasks: aitasks/t2173/t2173_1_*.md
Archived Sibling Plans: aiplans/archived/p2173/p2173_*_*.md
Base branch: main
Output branch: main
plan_verified:
  - claudecode/opus5_5 @ 2026-11-01 00:00
---

# t2173_2 — Two-pane `TrailSelectScreen`

Child of t2173 (parent plan: `aiplans/p2173_trail_select_two_pane_dialog_and_discovery_cache.md`,
approved 2026-10-31 after a review round). The parent's Context section explains the
measured costs (~3.3s per scan, 13 trails) and why the dialog is hard to scan.

### Verification notes (2026-10-31, verify pass before implementation)

Re-checked against `main` @ 7bdcd0911 (t2173_1 landed). The design holds; corrections:
- `TrailSelectItem` / `TrailSelectScreen` are at `board_trail_view.py:704` / `:744–:822`
  as stated. Only `board_widgets.PickerItem` is borrowed; the module imports no
  `Input`/`OptionList` yet (add them, plus `Vertical`).
- Textual 8.2.7 confirmed: `VerticalScroll.can_focus is True` (so the
  `can_focus=False` subclass is required); `Input` binds neither `up`/`down`,
  `pageup`/`pagedown` nor `ctrl+r`; `OptionList._on_click` sets `highlighted` and
  calls `action_select` without needing focus, so a click on the unfocusable list
  still posts `OptionSelected`. No App binds `ctrl+r`/`pageup`/`pagedown`.
- Host key routing: `KanbanApp.check_action` returns False for `nav_*` when
  `app.focused` is an `Input` (~:2466); `TrailsApp.check_action` does the same at
  :785. With Cancel focused both hosts' `nav_up/down` → `screen.focus_previous/next`
  (`aitask_board.py:4416`, `trails_app.py:725`), and the only two focusables are
  box + Cancel, so ↑ from Cancel lands on the box. KanbanApp's priority `escape`
  (`focus_board`, :2258) and `tab` (`focus_search`, gated off under a modal) are
  unchanged behaviour.
- `trails_app.py:412` (`isinstance(self.screen, TrailSelectScreen)` → `dismiss(None)`)
  is unaffected.
- **Test-site corrections:** in `tests/test_trails_app.py` the only `r` pressed
  *inside the selector* is :1617 (→ `ctrl+r`); :203 is the main-screen By-Trail
  local refresh and must stay `r` (there is no :2137 `r`). :1370–:1373 read
  `TrailSelectItem.render()` → read the list's option prompts. 
  `tests/test_board_detail_followup_kind.py:539` targets
  `FollowupKindPickerScreen`'s `#btn_dep_cancel`, not this dialog — **no change**.
- **Missed site, added:** `tests/test_board_bytrail_view.py:4765–4782` (t2112) asserts
  the generated-at label `· 07-10 17:00` / `· 2026-08-01` in the list rows. The label
  now lives in the detail pane, so the test asserts it in `trail_select_detail(...)`
  for each info (and on screen for the highlighted one), not in the list.
- **Review round (2026-10-31), two blocking concerns, both confirmed by Textual
  8.2.7 probes and folded in below:**
  1. *Literal list titles* — a `str` `Option` prompt is parsed as markup:
     `Option("Plan [bold]")` renders `Plan`, `Option(Text("Plan [bold]"))` renders
     `Plan [bold]`. So the list prompts must be `Text` (title + the `● open`
     marker appended as a styled span), otherwise a bracketed title displays
     differently from the string the title-only filter matches on.
  2. *Detail scroll on selection* — `Static.update()` inside a `VerticalScroll`
     keeps `scroll_y` (probe: 50 before and after replacing a 100-line body). The
     detail pane must scroll home whenever the shown handle changes.
- Other `isinstance(app.screen, ab.TrailSelectScreen)` waits
  (`test_board_bytrail_view.py:3741/3794/3901`, `test_trails_app.py` many) only check
  the screen type / `.infos` — unaffected.
- `tests/test_board_trail_view.py` `ModalDefaultCssTests` (:337–:380) measures
  `#dep_picker_dialog` at 0.6 and its negative control builds a plain modal with
  `#dep_picker_dialog`; both switch to `#trail_select_dialog` at 0.9.
- Docs: `reference.md:35–42` table and `:75`, `:98` ("`r` in the selector");
  `how-to.md:22` (`● open` rows — still true). `_index.md` and
  `workflows/implementation-trails.md` mention no selector `r` — no edit needed
  there. `board/reference.md:384` is the By-Trail footer, not the selector.
- t1647_5 (`TrailMergeSelectScreen`) is still `Ready` — Step 8e note stands.

### Design

`board/board_trail_view.py` — replace `TrailSelectItem` + the list body of
`TrailSelectScreen`. Constructor signature, `GuardedModalScreen`
base, `TRAIL_SELECT_RESCAN`, `open_handles`, `allow_rescan` and dismissal
values unchanged.

```
Container#trail_select_dialog            (90% × 80%, own ids — not #dep_picker_dialog)
  Label#trail_select_title     "Select trail" (bold)
  Label#trail_select_hint      two lines (see Hint)
  Horizontal#trail_select_body (1fr)
    Vertical#trail_select_left (40%, min-width 24)
      Input#trail_select_search   placeholder "Filter by title…"   (focused on mount, keeps focus)
      TrailTitleList#trail_select_list   OptionList subclass, can_focus=False; one Option per
                                         shown trail, id = handle, prompt = Text(title) [+ "  ● open" bold span]
    TrailDetailPane#trail_select_detail (1fr)   VerticalScroll subclass, can_focus=False
      Static#trail_select_detail_body
  Horizontal#trail_select_buttons
    Button "Cancel" #btn_trail_select_cancel
```

- **Focus model (settled)**: the search `Input` and the Cancel button are the
  only focusable widgets. Both the list and the detail pane are
  `can_focus=False` subclasses — a focused detail pane would re-activate both
  Apps' priority `nav_up/nav_down` (focus moves instead of scrolling). Tab /
  Shift+Tab cycle box ↔ Cancel; with Cancel focused, ↑/↓ follow each host's
  existing modal behaviour (back to the box). The detail pane scrolls with
  **PgUp/PgDn** (screen bindings) and the mouse wheel; ↑/↓ always belong to the list.
- **Keys**: screen `BINDINGS` `up`/`down` → the list's `action_cursor_up/down`,
  `pageup`/`pagedown` → the detail pane's `scroll_page_up/down` (non-priority:
  with the `Input` focused both Apps' priority `nav_up/down` are inactive, so
  arrows fall through to the screen); `Input.Submitted` → dismiss highlighted
  handle; `OptionList.OptionSelected` (click) → dismiss that handle; `escape` +
  Cancel → `None`; **`ctrl+r` → `TRAIL_SELECT_RESCAN` when `allow_rescan`** (a
  typed `r` must reach the search box).
- **Hint**: two lines so it fits 80×24 —
  `Type to filter · ↑/↓ move · Enter open · Esc cancel` and
  `PgUp/PgDn scroll details` (+ ` · Ctrl+R rescan` when `allow_rescan`).
- **List prompts are `Text`, never `str`** (review concern 1): a pure
  `trail_select_prompt(info, is_open) -> Text` builds `Text(_trail_select_title(info))`
  and appends `"  ● open"` with `style="bold"` — the same construction the removed
  `TrailSelectItem` used — so a title containing `[...]` renders literally and the
  displayed title is exactly the string the filter matches on.
- **Filtering**: `fuzzy_filter.rank(query, infos, key=_trail_select_title)` —
  title only (`doc.title or info.name or info.handle`, factored out of the old
  row code); blank query = original order; highlight resets to the first match;
  no match → empty list and the detail pane says `No trail title matches "<q>"`;
  Enter with no match does nothing.
- **Detail pane** — pure `trail_select_detail(info, overlap_notes, is_open) ->
  Text` (headless-testable, every value appended as `Text`, never markup):
  title (+ `● open`), handle; Owner `t<id>` + `(archived)` / `(folded)`; Scope
  kind; Freshness `_trail_stored_freshness(info)`; Generated
  `trail_generated_label(raw) or raw or "?"`; a **Shared tasks** block from
  `compute_trail_overlaps` (`<ref> — also in <other title>`); for `load_error`
  trails an **Error** block and the recorded `versions` fallback. Re-rendered
  on `OptionList.OptionHighlighted` and after each filter change, through one
  `_show_detail(handle)` method that tracks the handle shown last
  (`self._detail_handle`): when the handle differs (a new highlight, a filter that
  changes the first match, or the no-match message ↔ a trail), it calls
  `detail_pane.scroll_home(animate=False)` after updating the body (review
  concern 2), so a newly selected trail always opens at its title. Re-rendering
  the *same* handle (a filter that keeps it highlighted) keeps the reader's scroll
  position.
- **CSS**: own `DEFAULT_CSS` covering every rule above plus a visible
  highlight for the unfocused list
  (`#trail_select_list > .option-list--option-highlighted`), per
  tui_conventions "Modals pushed by multiple Apps".
- Remove `TrailSelectItem`; drop it from `aitask_board.py`'s re-export (:125)
  and the export lists in `tests/test_board_trail_view.py` (:63, :207). If
  `PickerItem` becomes unused in `board_trail_view.py`, keep it only if
  `LinkedTrailItem` still uses it (it does).

### Steps

1. Implement the screen + `TrailTitleList` + `TrailDetailPane` +
   `trail_select_detail` + `trail_select_prompt` + `_trail_select_title` in
   `board_trail_view.py`;
   update the `TRAIL_SELECT_RESCAN` comment (`r` → Ctrl+R) and the module
   docstring if needed.
2. Tests:
   - `tests/test_board_trail_view.py` `ModalDefaultCssTests`: `#trail_select_dialog`
     at 0.9 width; scoping negative control with a plain modal reusing that id.
     Unit tests for `trail_select_detail` (owner archived/folded, shared tasks,
     error + versions, generated label) and `_trail_select_title`.
   - `tests/test_board_bytrail_view.py` (:685–:810): highlight moves on `down`
     and changes the frame while the search box keeps focus; overlap note shows
     in the detail pane and not in the list; last option reachable (scrolled
     into view), Cancel visible; hint not truncated at 80×24.
     Adapt the t2112 generated-label test (:4765) to the detail pane.
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
   - **Scroll reset on selection change, in both hosts** (review concern 2): two
     trails whose details both overflow — PgDn on the first until `scroll_y > 0`,
     then `down` → the second trail's detail shows with `scroll_y == 0` and its
     title line visible; same sequence through filtering (type a query whose first
     match is the other overflowing trail) → `scroll_y == 0`. Control: re-typing a
     query that keeps the same trail highlighted leaves `scroll_y` unchanged.
   - **Literal titles** (review concern 1): a trail titled `Plan [bold] x` renders
     `Plan [bold] x` in the list row (rendered line, not the option's stored
     prompt) and in the detail pane; typing `[bold]` keeps it matched; unit test that
     `trail_select_prompt` returns `Text` with and without the open marker.
   - `tests/test_trails_app.py`: :1617 `pilot.press("r")` → `ctrl+r` (keep :203);
     :1370 query the list's option prompts instead of `TrailSelectItem`;
     `test_a_stale_selector_key_pops_nothing` unchanged.
   - `tests/perf/trails_pilot_bench.py`: select the trail by highlighting the
     option whose id is the handle (or typing its title), not by focusing a
     `TrailSelectItem`.
3. Docs: `tuis/trails/reference.md` "In the trail selector" table (type to
   filter, ↑/↓, Enter or click, PgUp/PgDn, Ctrl+R, Esc) and a sentence on the
   two panes; `reference.md` :75 and :98 "`r` in the selector" → Ctrl+R;
   `how-to.md` "Rows for trails that are already open are marked `● open`" (keep).
   Run `cd website && python3 check_links.py --build`.
4. Step 8e: `./ait note 1647_5 --from 2173_2` — `TrailSelectItem` is gone; model
   `TrailMergeSelectScreen` on the two-pane `TrailSelectScreen` (search box +
   `TrailTitleList` + `trail_select_detail`); overlaps now render in the detail
   pane. Hedge: the note's SHA dates it.
5. Step 9 (Post-Implementation): archive this child; the parent t2173 still has
   t2173_3 (manual verification) pending, so it stays open.

## Verification

- `bash tests/run_all_python_tests.sh` — last line `PYTHON SUITE: PASSED`.
- Manual, both TUIs, 80×24 and a wide terminal: type to filter, ↑/↓, Enter, click, PgUp/PgDn on a long detail pane, Tab cycle (box ↔ Cancel), Ctrl+R (`ait trails` only), Esc, an error trail's detail pane.
- `cd website && python3 check_links.py --build`.
- Step 8e note to t1647_5.

## Risk

### Code-health risk: low
- The dialog rewrite changes keyboard routing in two Apps that bind arrows with `priority=True`; a host whose `check_action` does not fall through for the focused `Input` would lose ↑/↓, and a focusable detail pane would re-activate the priority arrows · severity: low · → mitigation: none (covered in-plan by the both-host key + focus-cycle tests in step 2)
- ~6 test files and the perf bench need migration with the dialog · severity: low · → mitigation: none

### Goal-achievement risk: low
None identified.
