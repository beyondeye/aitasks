---
Task: t2211_9_sitrep_tui_detail_and_list_refinements.md
Parent Task: aitasks/t2211_sitrep_two_pane_window_with_sitrep_tui.md
Sibling Tasks: aitasks/t2211/t2211_4_*.md, aitasks/t2211/t2211_5_*.md, aitasks/t2211/t2211_6_*.md, aitasks/t2211/t2211_7_*.md, aitasks/t2211/t2211_10_*.md
Archived Sibling Plans: aiplans/archived/p2211/p2211_*_*.md
Base branch: main
Output branch: main
---

# t2211_9 — sitrep TUI: one-line priority/effort, a visible `d` toggle, created time, label filter

## Context

User-requested UI refinements after t2211_3 (706bf2f6d) landed. Presentation and
per-session UI state only: nothing changes in the store format, the writer, or
`lib/sitrep_*.py`. No docs are written here: t2211_6 (docs) and t2211_7 (manual
checklist) each get an `ait note`.

Reality checks (done during planning, HEAD 87b720e7c):
- `git diff HEAD -- .aitask-scripts/sitrep_tui/ tests/test_sitrep_tui_*.py` is
  empty. Re-check before editing (shared dirty worktree; other sessions edit
  other files).
- `task_yaml.parse_frontmatter` returns `created_at: "2026-11-09 10:04"` as a
  `str` (the loader does not make datetimes) and `labels` as a `list`.
  `aitask_create.sh get_timestamp` = `date '+%Y-%m-%d %H:%M'`, i.e. **local
  wall-clock time, no zone**.
- Textual 8.2.7: `App._check_bindings` falls through to the next binding of the
  same key when `run_action` is refused by `check_action`, and
  `Screen.active_bindings` skips a `False` binding. The footer reads
  `Binding.description` from the live `node._bindings` maps.
  `ShortcutsMixin._relink_live_bindings` already edits `self._bindings`, and
  must assign a **new list** per key, never mutate one in place: `BindingsMap.copy()`
  is shallow and in-place changes leak into later instances of the class (t2014).
- Keys in use: `q enter d l s j ? r x R A p b P`. Planned by siblings: t2211_4
  `t w T` and a `?q`-style dialog; t2211_10 picks its key after this task lands.
  Free and unclaimed: **`f`** (filter by labels) and **`F`** (clear the filter).
- `task_ref_id(item)` is non-None only for `kind == task` items with a local ref.
  `task_metas` covers exactly those, so labels and created_at follow the same rule.

## Implementation steps

### Pre-phase (risk mitigations)

1. [real_pane_repro] Before any edit, reproduce the user's "`d` only works when
   an item is selected" report in a real terminal.
   - Start a throwaway tmux server: `tmux -L t2211_9_probe new-session -d -x 100 -y 14`.
     Never the user's default server, and never `kill-server` on anything but
     this socket.
   - **Never point the probe at the live store.** `./ait sitrep tui` →
     `main()` builds the app with `startup_harvest=True`, and `_start_actions`
     then runs `harvest all` + `refresh`. Those write store items and harvest
     receipts. Isolate the files, not just the panes. The probe:
     - uses a small harness in the scratchpad
       (`<scratchpad>/t2211_9_probe/harness.py`, kept outside the fixture dir);
     - builds the tests' own fixture with
       `tests/test_sitrep_tui_app.py:build_fixture(<scratchpad>/t2211_9_probe/fx)`;
     - unsets `AITASK_SITREP_DIR` and sets `AITASK_SITREP_NOW` to a fixed instant;
     - asserts that `realpath(root)` and `realpath(store_dir)` both lie under
       `<scratchpad>/t2211_9_probe/fx`, and aborts otherwise;
     - runs `SitrepTuiApp(root, store_dir, startup_harvest=False,
       roles_probe=None).run()`, so no harvest/refresh worker and no agent poll
       start;
     - presses only `d`, `tab`, Enter / Escape and mouse clicks (never `r x R A p b P`).
   - **Write-destination control.** The decisive controls are:
     - the realpath assertions above (every destination is inside the fixture);
     - `startup_harvest=False`;
     - the `sha256sum` of every file under the **fixture** store before and
       after the probe. It must be unchanged, because the toggle writes
       nothing.
     The live `.aitask-sitrep/` is hashed before and after **for information
     only**. Other active sessions legitimately write that shared store, so a
     difference there is recorded as *inconclusive* unless its source is
     established (e.g. a writer `rev` / `git log` naming another session). It
     never counts as proof that the probe wrote to it, and an unchanged live
     store is not required. Record both comparisons and their interpretation in
     the Final Implementation Notes.
   - Run the harness in that tmux server with the venv Python:
     `~/.aitask/venv/bin/python <harness>`.
   - Press `d` in each state, with `capture-pane -p` before and after:
     - (a) an item highlighted;
     - (b) a click on a group header row (no item highlighted);
     - (c) `tab` to the situation pane;
     - (d) after opening and closing a details screen.
   - Record the observed outcome per state in the plan's Final Implementation
     Notes.
   - If any state does NOT toggle, find its cause (the focused widget's own
     binding for `d`, `check_action`, or a modal) and fix it in step 6, with a
     test that is red before the fix.
   - Tear down with `tmux -L t2211_9_probe kill-server`.

### 1. `sitrep_tui_model.py`: TaskMeta gains `created_at` and `labels`

- `TaskMeta`: add `created_at: str = ""` and `labels: tuple = ()`. Defaults keep
  the existing `TaskMeta(...)` equality assertions valid.
- `task_meta()`:
  - `created_at`: the `text("created_at")` value, which is already
    whitespace-collapsed and capped at 40 chars;
  - `labels` via a new `_labels(value) -> tuple`:
    - a list/tuple → each `str` item whitespace-collapsed, capped at 40 chars,
      empty items dropped, deduplicated in order;
    - a non-empty `str` → `(that,)`;
    - anything else → `()`.
  - It never raises. Any failure keeps the existing `False` / blank paths.

### 2. `sitrep_tui_model.py`: the "Created" cell and its rule

```python
CREATED_W = 10      # "YYYY-MM-DD"
_CREATED_FORMATS = ("%Y-%m-%d %H:%M", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d")

def parse_created(value: str) -> "_dt.datetime | None": ...   # naive local; None on anything odd

def created_cell(meta, now, tz=None) -> str:
    """''  (item names no local task) | '—' (file not found / no created_at) |
    '?' (unparsable) | 'HH:MM' (created today) | 'MM-DD' (this year) |
    'YYYY-MM-DD' (an earlier or later year: day precision is kept). Never raises."""
```

- **The pinned rule.** `created_at` is local wall-clock time (the writer's
  `date`). `now` is the TUI's instant (`resolve_now()`, which honours
  `AITASK_SITREP_NOW`, UTC). It is converted with `now.astimezone(tz)`, where
  `tz=None` means the machine's local zone (the same zone the writer stamped
  in). "Today" is equal calendar dates in that zone.
- Formats:
  - a date-only value created today shows `today`;
  - the same year shows `MM-DD`;
  - other years show the full `YYYY-MM-DD`, so tasks from different days of one
    old month stay distinguishable.
  - Every value fits in `CREATED_W` (10). The header "Created" is padded to it.
  - Cost: the "What to do" text starts 3 cells further right than a 7-wide
    column would put it. Accepted, because the day precision is the point of
    the column.
- `created_text(meta) -> str` for the details: the stored value verbatim, or
  `unknown`.

### 3. `sitrep_tui_model.py`: columns built in one loop

- `COLUMNS = (("Item", 5), ("Checked", AGE_CELL_W), ("Pri/Eff", PRI_EFF_W),
  ("Created", CREATED_W), ("What to do", 0))`.
- `header_text(cid_w)` and `row_text(item, now, cid_w, refresh_check, meta, tz=None)`
  both go through one `_cells(values, cid_w)` helper:
  - it pads each fixed column to its width (the first column to `cid_w`);
  - it appends the free text last.
  - They align by construction. The existing tests index `header.index("Pri/Eff")` /
    `"What to do"`, so they keep working.
- `row_text` adds `created_cell(meta, now, tz)`. `_refresh_ages` already
  recomputes `row_text` with a fresh `now` on every unchanged tick and relabels
  only the rows that changed. So the cell turns from `23:59`-style to `MM-DD` at
  midnight with no reparse. A test pins this.

### 4. `sitrep_tui_model.py`: label helpers (pure)

- `label_counts(store, metas) -> list[(label, n)]`: the labels on the store's
  task items (all groups, closed ones included), sorted by label.
- `filter_match(item, meta, labels: frozenset) -> bool`:
  - an empty filter → `True`;
  - otherwise `bool(meta) and set(meta.labels) & labels` (**any** selected label
    matches, i.e. OR).
  - **Non-task items** (triage, decisions, watches, pushes, xrefs) and task
    items whose file is missing are **hidden while a filter is active**. They
    carry no labels.
- `group_items` is unchanged: filtering happens in the app's `_rebuild_list`, so
  the group order rule stays in one place.

### 5. `sitrep_tui_app.py`: priority and effort on one line

`ItemDetailScreen.body_content`: replace the two `Priority` / `Effort` lines with

```python
Content.assemble(("Priority".ljust(_LABEL_W), "bold"), meta.priority or "?",
                 " · ", ("effort ", "bold"), meta.effort or "?")
```

Both labels are styled and both values are plain `str` parts (t2017). Add
`_field("Created", model.created_text(meta))` after `Task status`.
`LabelledDetailsTests.LABELS`: drop `"Effort"` and add `"effort"` and `"Created"`.

### 6. `sitrep_tui_app.py`: the `d` toggle becomes a visible toggle

- **Footer label.** The binding's default description becomes `"Show done"`.
  New `_set_binding_label(action, text)`:
  - for every key in `self._bindings.key_to_bindings`, it rebuilds that key's
    list as a **new list**, with `dataclasses.replace(b, description=text)` for
    the bindings whose `action == action`. Lookup is by action, so a remapped
    key works too;
  - then it calls `refresh_bindings()`.
  - `action_toggle_closed` sets `"Hide done"` / `"Show done"` from the new state.
- **Header.** `_render_header` appends `· N done, M dismissed hidden` while the
  closed groups are hidden and either count is > 0. A zero part is omitted:
  `· 2 dismissed hidden`. The counts are of closed items **that pass the
  label filter**, i.e. the items `d` would reveal. `action_toggle_closed` and
  the filter actions call `_render_header()`; today only `_apply` does.
- **Highlight on show.** `_rebuild_list(focus_slot=None)`: when the toggle turns
  the closed groups ON, it passes `focus_slot="done"`. After the rebuild the
  highlight moves to the first visible item of the first non-empty closed group
  (`done`, else `dismissed`). `OptionList.highlighted` scrolls it into view.
  On hide, or when no closed item is visible, the existing keep-by-cid /
  clamp-by-position rule applies unchanged.
- **The "only when an item is selected" report.** See Pre-phase
  `real_pane_repro`. If a genuine focus/selection dependency is found, fix it
  where it lives and pin it with a red-first test. The pilot probe on
  2026-11-09 found none.

### 7. Label filter: dialog, keys, header, rebuild

- **`LabelFilterDialog(GuardedModalScreen)`** in `sitrep_tui_actions.py`, next
  to the other dialogs, reusing `_DIALOG_CSS`:
  - a title, then a `SelectionList[str]` with one `Selection(Text(f"{label} ({n})"),
    value=label, initial_state=label in active)` per `label_counts` row. A
    `Text` prompt keeps the task-file text from being parsed as markup;
  - an active label no longer present on any item is still listed (`(0)`), so
    it can be unchecked;
  - buttons Apply / Clear / Cancel. Space toggles (owned by SelectionList),
    Enter applies (the board's `IssueTypeFilterScreen` `on_key` pattern), and
    Escape cancels;
  - it returns the chosen label list in display order, `[]` (clear) or `None`
    (cancel).
  - It is a plain GuardedModalScreen (no ShortcutsMixin), like the t2211_3
    dialogs, so `lib/shortcut_scopes.py` needs no row.
- **App state:** `self._label_filter: frozenset = frozenset()`. This is
  per-session UI state, never written anywhere.
- **Bindings** (app BINDINGS, after `s`):
  - `Binding("f", "filter_labels", "Labels")`;
  - `Binding("F", "clear_label_filter", "Clear filter")`.
  - Both go in `_MAIN_ACTIONS`.
  - `check_action`:
    - `filter_labels` → False when there is no label in the store and no filter
      is active;
    - `clear_label_filter` → False unless a filter is active.
  - Each action re-checks its precondition inside the action, because a binding
    gate is not a guard.
- **`action_filter_labels`** pushes the dialog with a callback:
  - `None` → nothing;
  - anything else → set `_label_filter`, `_rebuild_list()`, `_render_header()`.
- **`action_clear_label_filter`**: empty the set, rebuild, and re-render the
  header.
- **`_rebuild_list`**:
  - items not passing `filter_match` are skipped;
  - group headers count only visible items;
  - the highlight rule is unchanged (a hidden highlighted item hands the
    highlight on by position).
- **Header** while active: `· filtered by: sitrep, tui · N hidden (F clears)`,
  where:
  - `N` counts the items in the *currently shown* groups that the filter hides;
  - the labels are sorted, plain text via `_text`;
  - the key shown is the effective key (`self.key_for("clear_label_filter")`;
    check that `key_for` resolves non-ACTION_BINDINGS actions, else use
    `keybinding_registry.resolve_key`).
- **Store reloads keep the filter.** `_apply` → `_rebuild_list` applies it
  against the fresh `_metas`.

### 8. Notes to siblings (after the code commit)

- `./ait note 2211_6 --from 2211_9`:
  - keys `d` (Show/Hide done, header counts, jumps to the first closed item),
    `f` / `F`;
  - the Created column and its rule;
  - the one-line Priority · effort and the Created detail line.
- `./ait note 2211_7 --from 2211_9`: the manual checklist items (see
  Verification).
- `./ait note 2211_10 --from 2211_9`: `f` and `F` are now taken.
- t2211_4 already lists its keys `t w T`, and `f` / `F` do not collide; send
  it a one-line note anyway so its key table stays current.

### Post-phase (risk mitigations)

1. [binding_label_no_leak_control] Pilot tests:
   - (i) a second `SitrepTuiApp` built after the first one toggled `d` starts
     with `Show done`, and the class-level `_merged_bindings` description is
     unchanged;
   - (ii) with a key override `d → D` installed through the keybinding registry's
     test seam (as the existing remap tests do), `D` toggles and the label still
     flips.
   - Mutant control, on an isolated scratch copy of the module (never the shared
     worktree): make `_set_binding_label` mutate the existing per-key list in
     place. (i) must turn red. Record the result.
2. [rebuild_highlight_matrix] One parametrised pilot test over:
   - filter {off, on};
   - closed groups {hidden, shown};
   - the highlighted item {stays visible, gets hidden by the change}.
   It asserts the highlight lands on the same cid when that item is still
   visible, else on the item at its position clamped to the last row. The one
   exception is the show-closed jump, which lands on the first closed item.

## Tests

In `tests/test_sitrep_tui_actions.py`, which has the `t10_demo.md` / archived
`t20` fixture: extend the fixture frontmatter with `created_at` and `labels`.

- **Model:**
  - `created_cell` table (tz=UTC passed explicitly):
    - today `10:04`, a date-only value today → `today`;
    - same year `11-08`;
    - last year `2025-12-03`, and `2025-12-04` is distinct from it (day kept);
    - a next-year value (clock skew) `2027-01-02`;
    - missing → `—`, garbage / `2026-02-31 10:00` → `?`;
    - None → `""`, False → `—`;
    - all ≤ `CREATED_W`.
  - The midnight case: the same meta at `23:59` local → `HH:MM`, at `00:01` the
    next day → `MM-DD`.
  - A non-UTC `tz` (fixed +05:00) case shows that the conversion is applied.
  - `_labels` shapes: list, str, int, nested, duplicates, hostile `[b]x[/b]`
    kept literal.
  - `filter_match` truth table: task with or without the label, a non-task item,
    `False` meta, an empty filter.
- **TaskMeta tests:** the existing equality assertions still hold; new fields
  are read; a broken frontmatter never raises.
- **Rows:**
  - the Created cell sits under the "Created" header (`header.index` slicing);
  - `What to do` is still aligned;
  - non-task rows are blank;
  - `_refresh_ages` across a seam-moved midnight relabels the row without
    `load_snapshot` (patch it to raise).
- **Details:**
  - `"Priority    high · effort low\n"`;
  - `"Created     2026-11-09 10:04"`;
  - `LabelledDetailsTests.LABELS` updated, and its styled-spans-are-labels test
    passes.
- **`d` toggle (pilot):**
  - from four focus states (list focused with a highlight; list focused with
    `highlighted=None`; the situation pane focused; `set_focus(None)`) `d`
    flips `_show_closed` and the `hdr:done` row appears or vanishes;
  - `active_bindings["d"].binding.description` reads `Show done` → `Hide done`
    → `Show done`, and the footer text shows it;
  - a second app instance created after the first toggled still starts at
    `Show done` (pins the no-leak rule, t2014);
  - the header contains `done, ` / `dismissed hidden` with the right counts
    while hidden, and not while shown;
  - in a short pane (`size=(100, 10)`) showing highlights the first done item,
    and its line is inside the list's viewport (`scroll_y` ≤ line <
    `scroll_y` + content height, using OptionList's option→line mapping,
    probed at implementation time);
  - hiding again keeps the existing clamp rule.
- **Label filter (pilot):**
  - `f` opens the dialog listing labels with counts;
  - choosing one label and applying (Enter) leaves only the matching task rows,
    with non-task rows hidden;
  - the header says `filtered by:` with the hidden count;
  - `F` clears;
  - Esc cancels with no change;
  - bindings matrix: `f` hidden with no labels, `F` hidden with no filter, both
    hidden on details;
  - a reload (`_apply` of a fresh snapshot) keeps the filter;
  - a hostile label renders literally in the dialog and the header;
  - the filter is not written to the store (the `todo.md` digest is unchanged).
- Run:
  - `~/.aitask/venv/bin/python -m pytest tests/test_sitrep_tui_app.py tests/test_sitrep_tui_actions.py -q`;
  - then `bash tests/run_all_python_tests.sh --test-dir tests` (read the last
    line);
  - `bash tests/test_no_raw_tmux.sh`.

## Verification

- The tests above, plus the full Python suite verdict line.
- Manual check in a real sitrep window (also the t2211_7 note):
  - the Priority · effort details line and the Created line;
  - `d` in a short pane jumps to the first done item, the footer reads Show
    done / Hide done, and the header gives the hidden counts;
  - Created shows `HH:MM` on today's task rows and `MM-DD` on older ones;
  - `f` filters by a label, the header says so, and `F` clears.

## Step 9 (Post-Implementation)

Commit the code (`enhancement: … (t2211_9)`), commit the plan with
`./.aitask-scripts/aitask_task_commit.sh`, send the notes in step 8, then
archive via the workflow's Step 9.

## Risk

(Re-assessed once, with the inline phases included: both levels stay
`medium`. The phases add detection, but they change neither what the work
touches nor how open the cause of the user's report still is.)

### Code-health risk: medium
- Swapping the `d` binding's description edits the live `self._bindings` map. An
  in-place list mutation would leak the label into later app instances (t2014),
  and a wrong lookup would break a user's remapped `d` · severity: medium · → mitigation: inline post-phase binding_label_no_leak_control
- A new column and the filter change `_rebuild_list`, the row layout and the
  header, which ~60 existing pilot tests pin. The highlight-keeping rule now has
  a third input (the filter) · severity: low · → mitigation: inline post-phase rebuild_highlight_matrix

### Goal-achievement risk: medium
- The user's "`d` only works when an item is selected" report may have a cause
  other than the off-screen groups (e.g. a focus state the headless pilot does
  not reproduce). In that case the visible-state fix ships without fixing what
  the user saw · severity: medium · → mitigation: inline pre-phase real_pane_repro

### Planned mitigations
- timing: pre-phase | name: real_pane_repro | type: test | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: goal-achievement: user's d-toggle report may have another cause | desc: reproduce the d report in a throwaway tmux server across focus states before editing
- timing: post-phase | name: binding_label_no_leak_control | type: test | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: code-health: live binding-label swap leak / remap | desc: second-instance + remapped-key label tests with an in-place-mutation mutant control
- timing: post-phase | name: rebuild_highlight_matrix | type: test | priority: low | effort: low | inline_risk: low | added_complexity: low | addresses: code-health: _rebuild_list gains the filter input | desc: parametrised highlight-rule test over filter x closed x hidden-highlight
