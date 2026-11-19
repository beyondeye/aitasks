---
Task: t2334_sitrep_tui_item_type_tabs.md
Base branch: main
Output branch: main
---

# t2334 — Sitrep TUI item-type tabs

## Context

`ait sitrep tui` shows every item in one list, grouped only Now / Next /
Waiting. Triage questions, picks, push reminders, watches and crash-recovery
items are mixed together, so "what do I have to triage" or "what crashed" is
hard to see once there are more than a dozen items. This adds a one-row tab
strip above the list — **All · Triage · Tasks · Recovery · Watches**, each with
its open count — that filters the list by item type, cycled with left/right
(wrapping) or by mouse click. The grouping, the `d` closed toggle and the label
filter keep working inside a tab. Tab state is per-session UI, never stored.

## Design decisions

- **Mapping lives in the model, keyed by `classify`.** One table
  `CLASS_ITEM_TYPE` in `sitrep_tui_model.py` maps every `NEXT_STEPS` key to an
  item type (`triage` / `tasks` / `recovery` / `watches`) or to the sentinel
  `BY_KIND`. The by-kind rows are `done`, `dismissed`, `unknown`,
  `unknown_manual` and `raw`: they resolve by the item's kind
  (`KIND_ITEM_TYPE`: question→triage, task→tasks, but a task whose ref is a
  `recover:` ref (`st.parse_recover_ref`) →recovery, action→tasks,
  watch→watches). An unknown kind (the writer refuses those, `st.KINDS`) falls
  back to `tasks`. That covers "`unknown*` items go to the tab of their kind"
  and also covers closed items once `d` shows them.
- **Tabs are descriptors.** `ListTab(id, label, short, item_type)` (frozen
  dataclass). `item_type=None` means every item (All). `LIST_TABS` is a tuple
  of those. The app keeps only the active tab **id** (`self._tab`, default
  `"all"`). The strip renders from the descriptors. A later "Directions" tab can
  be added as another descriptor type that the app renders differently. There
  is no enum and no `if tab == …` chain.
- **Counts** = items of the type with `state == "open"` (the same rule the
  header's "N open in Now" uses), **without** the label filter applied, so a
  tab's number stays steady. `unknown` rows are not counted, but they still
  appear in their tab's list, so a tab can read `Triage 0` and still list an
  unknown question. What the label filter (and
  `d`) hides in the **active tab** is reported by the existing header note
  `_visibility_note`, which is now scoped to the active tab.
- **Widget: a new small `ItemTabStrip` in `sitrep_tui_widgets.py`, modelled on
  `TrailTabStrip`, not imported from it.** `TrailTabStrip`
  (`board/trails_app.py:172`) lives inside the trails App module, which pulls in
  the board widget layer, and its click handler calls the trails App's private
  `_select_trail_tab`. So it does not fit without dragging board imports in. The
  same pattern is reused: a `Static` that draws synchronously, records cell
  spans and maps clicks. Here a click posts an `ItemTabStrip.Selected(tab_id)`
  message instead of calling the app. The module docstring will say why it is
  not reused.
- **Elision — measured layouts plus a budgeted last resort, so all five
  targets survive at 30 columns whatever the counts.** A pure
  `strip_segments(rows, width)` helper in the widgets module measures each
  candidate with the **actual** count strings and picks the first that fits:
  1. **full**, padded: ` All 14 │ Triage 3 │ Tasks 6 │ Recovery 2 │ Watches 3 `
  2. **short**, padded: ` All 14 │ Tri 3 │ Tsk 6 │ Rec 2 │ Wat 3 ` (~40 cells with these counts)
  3. **compact**: no padding, no space before the count: `All14│Tri3│Tsk6│Rec2│Wat3`
  4. **mnemonic, exact**: each tab shows its **one-character mnemonic** plus
     its **exact** count, with bare separators: `A10000│?1000│T1000│R100│W7900`
     (29 cells). The mnemonic is a new descriptor field `mark`: All `A`,
     Triage `?`, Tasks `T`, Recovery `R`, Watches `W`. They are distinct by
     construction, and a test pins that, so no two tabs ever read the same.
     Like every layout above, it is measured as a whole row and used when it
     fits. No count is capped while the exact row fits.
  5. **mnemonic, capped** — only when the exact mnemonic row itself exceeds the
     width: each of the n tabs gets `budget = (width - (n-1)) // n` cells (5 at
     width 30), which leaves `allowed = budget - 1` cells for the count. A count
     with more than `allowed` digits is capped to `allowed - 1` nines plus `+`
     (at width 30: 10000+ → `999+`). Counts that fit their budget stay exact.
     This always fits once `width >= n*3 + (n-1)` (19 for five tabs). Below
     that the CSS `text-overflow: ellipsis` clips, and the helper docstring and
     the docs say so. 30 columns is the documented supported minimum.

  The active tab is marked by `bold reverse` styling, so it stays visible
  without padding. The strip re-lays out on `on_resize`. The click spans come
  from the segments actually drawn, so they always match what is visible.
- **Keys:** `Binding("left", "prev_tab", "Prev tab", show=False, priority=True)`
  and `Binding("right", "next_tab", "Next tab", priority=True)` in
  `SitrepTuiApp.BINDINGS`, under the `sitrep_tui` shortcut scope. Bindings are
  scanned from source (`lib/shortcut_scopes.py`), so they are remappable with no
  registry edit. `priority` is needed because the focused `OptionList` has its
  own left/right scroll bindings. Both actions go into `_MAIN_ACTIONS`, so
  `check_action` returns False on any pushed screen. A False check makes
  Textual's `run_action` return False, so the key falls through to the
  sub-screen's TextArea or dialog. This is the same mechanism the existing
  priority `enter` binding relies on.
- **Selection:** a store reload keeps the active tab. `_rebuild_list`'s
  existing keep-by-cid / nearest-row logic then applies within the tab
  (membership is added to `_passes`). On a **tab switch** the highlighted item
  stays when it is in the new tab, otherwise the highlight goes to the first
  row (no "nearest position" in an unrelated list). That first-row rule sits
  **inside** the existing `elif order:` guard, so an empty order (the empty
  Recovery tab, or a tab the label filter empties) leaves `target = None` and
  no highlight set. The only option is then the disabled `empty` line, and
  `open_item` stays hidden because `_selected_cid()` is None.
- **Empty tab:** a type tab with no visible row shows one disabled option
  (`id="empty"`), `Nothing in <Label>.`, in place of the group headers. Cycling
  never skips it. All keeps today's behaviour (headers with `(0)`), so the
  existing tests stay unchanged.

## Implementation steps

### 1. `sitrep_tui_model.py` — item types and tab descriptors

Add a section `# --- item-type tabs (t2334) ---` after `next_step`:

```python
BY_KIND = "by_kind"
ITEM_TYPES = ("triage", "tasks", "recovery", "watches")
CLASS_ITEM_TYPE = {
    "triage": "triage", "review": "triage", "decide": "triage",
    "pick": "tasks", "pick_xref": "tasks", "pick_noref": "tasks",
    "push": "tasks", "do": "tasks",
    "recover": "recovery",
    "watch": "watches", "watch_manual": "watches",
    "done": BY_KIND, "dismissed": BY_KIND, "unknown": BY_KIND,
    "unknown_manual": BY_KIND, "raw": BY_KIND,
}
KIND_ITEM_TYPE = {"question": "triage", "task": "tasks",
                  "action": "tasks", "watch": "watches"}

def item_type(item, refresh_check=None) -> str:
    """Never raises (render time)."""
    try:
        t = CLASS_ITEM_TYPE.get(classify(item, refresh_check), BY_KIND)
    except Exception:
        t = BY_KIND
    if t != BY_KIND:
        return t
    if item.kind == "task" and st.parse_recover_ref(item.ref or ""):
        return "recovery"
    return KIND_ITEM_TYPE.get(item.kind, "tasks")

@dataclass(frozen=True)
class ListTab:
    id: str
    label: str
    short: str
    mark: str                 # one distinct character, the narrowest form
    item_type: "str | None"   # None: every item

    def holds(self, item, refresh_check=None) -> bool: ...

LIST_TABS = (ListTab("all", "All", "All", "A", None),
             ListTab("triage", "Triage", "Tri", "?", "triage"),
             ListTab("tasks", "Tasks", "Tsk", "T", "tasks"),
             ListTab("recovery", "Recovery", "Rec", "R", "recovery"),
             ListTab("watches", "Watches", "Wat", "W", "watches"))

def tab_by_id(tab_id) -> ListTab  # falls back to LIST_TABS[0]
def tab_counts(store, checks) -> dict
    # {tab id: n items it holds with state == "open"}; store None (never
    # parsed, or the first parse failed) -> every tab 0. Never raises.
```

### 2. `sitrep_tui_widgets.py` — `ItemTabStrip`

- `strip_segments(rows, width) -> list[(tab_id, text, active)]`, where `rows`
  is `[(tab_id, label, short, mark, count, active)]`. It builds the full, short and
  compact layouts (see Design decisions), each measured with
  `rich.cells.cell_len` including separators and the real count strings, and
  returns the first that fits, in the order full → short → compact →
  mnemonic-exact. Only when none fits does it return mnemonic-capped. When
  the width is 0 or unknown (before the first layout) it returns full.
  Separators are `│` padded by a space in full/short, bare in compact and
  budgeted.
- `class ItemTabStrip(Static)`: CSS `height: 1; width: 100%; background:
  $panel; text-wrap: nowrap; text-overflow: ellipsis;`, `can_focus = False`,
  `markup=False`. `set_tabs(rows)` stores the rows and calls `_draw()`.
  `_draw()` builds a `rich.text.Text` (`│` dim separators, active
  `bold reverse`), records `_spans` and updates. `on_resize` calls `_draw()`.
  `tab_at(x)` returns the tab id under a cell. `on_click` posts `Selected(tab_id)`.
- `class Selected(Message)` carries `tab_id`.

### 3. `sitrep_tui_app.py` — wire it

- Import `ItemTabStrip`. In `compose`, yield `ItemTabStrip(id="st-tabs")` after
  the situation scroll and before `#st-columns`.
- `__init__`: `self._tab = "all"`.
- BINDINGS: the two arrow bindings above. Add `"prev_tab", "next_tab"` to
  `_MAIN_ACTIONS`.
- `_passes(item)`: also require
  `model.tab_by_id(self._tab).holds(item, self._checks.get(item.num))`.
  `_visibility_note` uses `_passes`, so it is automatically scoped to the active
  tab. In the label-filter count, compute hidden as "in tab, but fails the
  filter". Split `_passes` into `_in_tab` and `_label_ok` so the note counts
  only filter-hidden items of the active tab.
- `_render_tabs()`: counts from `model.tab_counts(self.store, self._checks)`,
  then `strip.set_tabs([(t.id, t.label, t.short, t.mark, n, t.id == self._tab) …])`.
  It is called at the end of `_rebuild_list`, so every reload, tab switch,
  toggle and filter change re-renders it. With `self.store is None` (damaged
  before start) the strip shows every tab at 0 and startup reaches the existing
  banner. After a later failed reload, `_apply` keeps the last good
  `self.store` (unchanged behaviour), so the strip keeps the last good counts.
- `_rebuild_list(focus_closed=False, tab_switched=False)`: when
  `tab_switched` and `prev` is not in the new order, the target is `order[0]`.
  When the active tab is not All and no row is shown, the options are only
  `Option(Text(f"Nothing in {tab.label}."), id="empty", disabled=True)`.
- `_select_tab(tab_id)`: does nothing off the main screen. Otherwise it sets
  `self._tab`, calls `_rebuild_list(tab_switched=True)` and `_render_header()`.
  `action_next_tab` / `action_prev_tab` step the index in `LIST_TABS` modulo its
  length. `on_item_tab_strip_selected(event)` calls `_select_tab(event.tab_id)`.
- Module docstring: one bullet for the tabs.

### 4. Docs

- `aidocs/framework/sitrep.md` "Views": a **Tabs** bullet. It covers the
  descriptor table, the `classify`-keyed mapping with by-kind rows, the counts
  rule, the arrow keys with priority/fall-through, that the tab is session
  state, and why `TrailTabStrip` is not reused.
- `website/content/docs/tuis/sitrep/`: `how-to.md` gets a short "Show one kind
  of item" passage next to the label-filter one. `reference.md` gets
  `←`/`→` rows in the Main list key table, and the header note now says it
  covers the active tab. `_index.md` gets a one-line mention if it lists the
  main-list features. Current-state prose only. Run
  `python3 check_links.py --build` in `website/`.

### 5. Tests — `tests/test_sitrep_tui_app.py`

A model-level `ItemTypeTabTests(_Case, unittest.TestCase)`:
- **Class coverage:** `set(CLASS_ITEM_TYPE) == set(NEXT_STEPS)`. Every value is
  in `ITEM_TYPES` or is `BY_KIND`, and `set(KIND_ITEM_TYPE) == set(st.KINDS)`.
  A new class or kind therefore cannot fall out of every tab.
- **Exactly one type tab per fixture item:** for every item in the fixture
  store (all states), exactly one non-All tab `holds` it, and All holds all of
  them. Spot checks: triage/review/question → triage; push/do/pick/xref →
  tasks; trailwatch/baddate → watches; done (action) → tasks; the unknown
  question → triage; a `recover:t42` `_item` → recovery, both open and done.
- **Counts:** `tab_counts` on the fixture equals hand-computed numbers of
  `state == "open"` items. Dismissed, done **and unknown** items are excluded
  (the fixture's unknown question and unknown t20 task are not counted).
- **Mnemonics:** the `mark`s of `LIST_TABS` are pairwise distinct and one cell
  wide. So are the `short`s.
- **`strip_segments`:** width 100 → full, 45 → short, 30 → compact (fixture
  counts). Then the mnemonic cases at width 30, each asserting total cells
  ≤ 30, all five ids present, and the texts pairwise distinct:
  (a) **exact 3-digit**: 300/100/100/100/100 → `A300│?100│T100│R100│W100`
  (mnemonic-exact), no `+`;
  (b) **equal 4-digit**: Triage 1000 and Tasks 1000 → `?1000` and `T1000`,
  exact and distinguishable;
  (c) **a five-digit count that fits**: 10000/1000/1000/100/7900 →
  `A10000│?1000│T1000│R100│W7900` (29 cells), exact, no `+`;
  (d) **exact counts that genuinely overflow**: all five at 10000 (exact row 34
  cells) → mnemonic-capped `A999+│?999+│T999+│R999+│W999+`. A mixed
  overflow, 30010/10000/10000/10000/10 (exact row 31 cells) →
  `A999+│?999+│T999+│R999+│W10`, where the count within its budget stays exact.
  (e) **exact-fit boundary**: 10000/10000/10000/10000/5 (exact row exactly 30
  cells) → mnemonic-exact `A10000│?10000│T10000│R10000│W5`, no `+`.
  Width 19 still fits five tabs (capped). Also check `tab_counts(None, {})` gives all
  zeros.

An app-level `TabTests(_AppCase)`:
- The strip shows `All N` active. `right` ×5 wraps back to All, and `left`
  from All goes to Watches. Each step leaves only that tab's rows in
  `app._order`.
- **Empty tab:** with no recovery item the Recovery tab shows `Recovery 0`, can
  be selected, and the list is the single disabled `empty` option.
  `ol.highlighted is None` and `open_item` is not shown. The same holds for a
  tab emptied by the label filter (Triage + filter `sitrep`).
- **Zero open, unknown row listed:** set the open triage and review questions
  to `done` (writer `set-state`), then reload. The strip reads `Triage 0` and the
  Triage list still contains the unknown question (`ids["question"]`).
- **Recovery tab with an item:** the `add` verb refuses `recover:` refs
  (`sitrep_todo.py:1111`), so create the item the way
  `RecoverPickTests.recover_item` does (`tests/test_sitrep_tui_actions.py:670`):
  `recovery-apply --ref recover:t30 --expect-rev absent --incarnation <inc>
  --state open --outcome "crashed · fixture evidence" … --context-file -` with a
  matching `incarnation=` origin. A local helper in the test file runs it through
  this file's `writer()`. Then `_poll_store`: Recovery shows 1 and lists it.
- **Narrow strip, rendered:** run at `SIZE`, then `pilot.resize_terminal(30,
  16)` and pause. The strip's rendered text holds all five compact labels
  (`All…`, `Tri…`, `Tsk…`, `Rec…`, `Wat…`) within 30 cells, and the active one
  carries the reverse style. For each tab, clicking the centre of its recorded
  span (`pilot.click("#st-tabs", offset=(x, 0))`) makes it active. Resizing back
  to 100 restores full labels.
- **Multi-digit counts, rendered:** at 30 columns, patch
  `appmod.model.tab_counts` (`mock.patch.object`) to return
  the counts for the **whole** test, so every re-render after a click keeps
  them. Then call `app._render_tabs()` and pause. For each of the five tabs in
  turn, click the centre of its recorded span and pause. After **each** click,
  assert against the strip's displayed line (its rendered content string):
  `app._tab` is that tab, the line is ≤ 30 cells, it reads exactly the expected
  text, and the clicked segment is the one carrying the reverse style. Run this
  for two count sets (subTests):
  - 10000/1000/1000/100/7900 → `A10000│?1000│T1000│R100│W7900` (exact, fits);
  - 10000 ×5 → `A999+│?999+│T999+│R999+│W999+` (capped, overflow).
- **Damaged store:** extend `test_a_store_damaged_before_start_shows_the_banner`
  (the strip reads `All 0` … `Watches 0`, the banner is visible) and
  `test_damage_keeps_the_last_good_view_under_a_banner` (the strip text is
  unchanged after the failed reload).
- **Composition with `d`:** in Tasks, `d` adds the done action (`Deployed`) and
  the dismissed task. In Watches, `d` adds nothing of another type.
- **Composition with the label filter:** the shared fixture's hostile row has
  no `ref`, and `task_ref_id` reads `item.ref`, so no fixture item carries a
  label. The test therefore adds its own row, in-test, so the shared fixture and
  the counts other tests assert stay unchanged: writer `add --kind task --title
  "t11 labelled" --ref t11 --group next`, then `_poll_store`. It then drives the
  **real** dialog the way `test_sitrep_tui_actions.py`'s label-filter tests do
  (`f`, Space on `sitrep`, Enter). In Tasks, only the t11 row is shown, and the
  header carries `filtered by: sitrep` with a hidden count equal to the other
  Tasks items. In Triage the same filter gives the empty line (no highlight),
  and the header reports the hidden triage items.
- **Reload keeps tab + selection:** in Tasks, select `pushref`, add a new item,
  then `_poll_store`. The tab is still Tasks and the selection is kept. Then
  dismiss the selected item and reload: the highlight moves to the nearest row
  within the tab.
- **Tab switch selection:** select the triage item in All, then switch to
  Triage: still selected. Switch to Watches: the first row.
- **Arrow fall-through on a sub-screen:** open details, press `left`/`right`.
  `app._tab` is unchanged and the details screen is still on top.
- **Remap:** with `keybinding_registry._OVERRIDES_CACHE = {"sitrep_tui":
  {"next_tab": "N"}}` (the pattern from `test_sitrep_tui_actions.py:1408`),
  `N` steps the tab. If the override is applied at app start, follow that
  test's setup exactly.

Run: `python3 -m unittest tests.test_sitrep_tui_app`, then
`bash tests/run_all_python_tests.sh --test-dir tests` (verdict from the last
line) for the `test_sitrep_tui_*` modules
(`test_sitrep_tui_actions.py` asserts footer and binding labels).

### Post-phase (risk mitigations)

- **arrow_fallthrough_test** — the `TabTests` case that opens the details
  screen and the label-filter dialog, presses `left`/`right`, and asserts
  `app._tab` is unchanged and the sub-screen is still on top (also that the
  details TextArea receives the key).
- **passes_split_composition_tests** — `_passes` split into `_in_tab` +
  `_label_ok`, with the `d` / label-filter composition cases in `TabTests`
  asserting both the rows and the header's hidden counts per tab.

## Verification

- `python3 -m unittest tests.test_sitrep_tui_app tests.test_sitrep_tui_actions tests.test_sitrep_tui_requests tests.test_sitrep_tui_trails tests.test_sitrep_tui_trails_actions`
- `bash tests/run_all_python_tests.sh --test-dir tests`, last line `PASSED`.
- `cd website && python3 check_links.py --build`.
- Manual sanity (optional): `ait sitrep tui` in a narrow pane shows short labels
  on one row.

## Step 9

After implementation: review, commit (`feature: … (t2334)`), then archive via
task-workflow Step 9.

## Risk

### Code-health risk: low
- Priority `left`/`right` bindings on the App could swallow arrow keys meant for a focusable widget (details TextArea, dialogs) if `_MAIN_ACTIONS` gating misses a screen · severity: low · → mitigation: inline post-phase arrow_fallthrough_test
- `_passes` now carries tab membership, so every consumer of it (header note, rebuild, closed-count) changes meaning at once · severity: low · → mitigation: inline post-phase passes_split_composition_tests

### Planned mitigations
- arrow_fallthrough_test · timing: after · disposition: inline · inline_risk: low · added_complexity: low
- passes_split_composition_tests · timing: after · disposition: inline · inline_risk: low · added_complexity: low

### Goal-achievement risk: low
None identified.
