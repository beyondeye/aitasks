---
Task: t806_keybinding_in_wizard_for_nod_selection.md
Worktree: (none — working on current branch)
Branch: main
Base branch: main
---

# t806 — Keyboard navigation + fuzzy filter for brainstorm wizard node selection

## Context

In the `ait brainstorm` TUI, the Actions wizard step-2 config for the
**Hybridize** (synthesize) and **Compare** operations renders a flat list of
`Checkbox` widgets per selection group (`_config_hybridize`, `_config_compare`
in `.aitask-scripts/brainstorm/brainstorm_app.py`). With many nodes this does
not scale: there is no filter, and only `Tab` moves focus (stepping one
checkbox at a time). The user wants:

- A fuzzy-search box per list (nodes for Hybridize; nodes **and** dimensions
  for Compare).
- `↑`/`↓` arrows to move focus **within** the focused list.
- `Tab`/`Shift+Tab` to cycle between **control groups** as wholes:
  node list → dimension list → section checkboxes → buttons → wrap.

The settings TUI already has a fuzzy picker (`FuzzySelect` in
`.aitask-scripts/lib/agent_model_picker.py`), but — as the user noted — it is
built for a single-list, single-select modal and is not a good fit here
(multi-list, multi-select, with arrow keys it would consume). So this task
adds a small **multi-select filterable checkbox-list widget** modelled on the
same "search box on top, scrolling list below" idea, and keeps the existing
native `Checkbox` widgets so selection-collection code is untouched.

Clarified with the user:
- **Tab cycles whole groups** (node list / dimension list / section
  checkboxes / buttons), not individual checkboxes.
- **Filter is view-only:** a checked item that no longer matches the filter
  stays checked and is still included in the operation.

## Files to modify

- `.aitask-scripts/brainstorm/brainstorm_app.py` — new widget class, the two
  config-step builders, `on_key` Tab/arrow handling, CSS.
- `tests/test_brainstorm_wizard_filter.py` — **new** unit test for the pure
  label-filter helper.

## Design

### New widget: `FuzzyCheckList(Container)`

Defined in `brainstorm_app.py` after `CompareNodeSelectModal` (~line 1563).
A self-contained group: an `Input` filter box on top + a `VerticalScroll` of
native `Checkbox` rows.

```python
class FuzzyCheckList(Container):
    """Filter box + scrolling multi-select checkbox list.

    Native Checkbox rows keep their caller-supplied CSS class, so existing
    `query("Checkbox.<class>")`-based collection code works unchanged.
    """
    def __init__(self, items, *, item_class, default_checked=False,
                 placeholder="Type to filter…", id=None):
        super().__init__(id=id)
        self._items = list(items)
        self._item_class = item_class
        self._default_checked = default_checked
        self._placeholder = placeholder

    def compose(self):
        yield Input(placeholder=self._placeholder, classes="fcl_filter")
        with VerticalScroll(classes="fcl_list"):
            for label in self._items:
                yield Checkbox(label, value=self._default_checked,
                               classes=f"{self._item_class} fcl_item")

    def on_input_changed(self, event: Input.Changed) -> None:
        visible = set(_filter_labels(event.value, self._items))
        for cb in self.query(Checkbox):
            cb.display = str(cb.label) in visible
        focused = self.app.focused           # filtered-out focused row?
        if isinstance(focused, Checkbox) and not focused.display:
            self.query_one(Input).focus()

    def on_key(self, event) -> None:         # ↑/↓ within this group only
        if event.key in ("up", "down"):
            if self._navigate(1 if event.key == "down" else -1):
                event.prevent_default(); event.stop()

    def _navigate(self, direction: int) -> bool:
        chain = [self.query_one(Input)] + [
            cb for cb in self.query(Checkbox) if cb.display]
        focused = self.app.focused
        cur = chain.index(focused) if focused in chain else None
        nxt = _next_checkbox_index(cur, len(chain), direction)
        if nxt is None:
            return True                      # boundary: consume, no move
        chain[nxt].focus(); chain[nxt].scroll_visible()
        return True
```

Notes:
- Reuses the existing `_next_checkbox_index` helper (line ~1451) for
  boundary-stop arrow math.
- Native `Checkbox` ⇒ `Space`/`Enter` toggle works for free; `Checkbox.Changed`
  bubbles to the app exactly as today.
- Filtering toggles `.display` only — `.value` (selection) is preserved on
  hidden rows, and hidden rows drop out of the focus chain automatically.

### New module-level helper (near `_next_checkbox_index`, ~line 1451)

```python
def _filter_labels(query: str, labels: list[str]) -> list[str]:
    """Case-insensitive substring filter. Blank query keeps everything.

    Order-preserving — matches the substring behaviour of the settings
    `FuzzySelect` picker.
    """
    q = query.strip().lower()
    if not q:
        return list(labels)
    return [lbl for lbl in labels if q in lbl.lower()]
```

### `_config_hybridize` (~line 4952)

Replace the `for nid … Checkbox(nid, classes="chk_node")` loop with:

```python
container.mount(Label("[bold]Select Source Nodes (2+)[/]"))
container.mount(FuzzyCheckList(list_nodes(self.session_path),
                               item_class="chk_node",
                               placeholder="Type to filter nodes…",
                               id="hyb_nodes"))
```

(Merge-Rules label + `TextArea` + `Next ▶` button unchanged.)

### `_config_compare` (~line 4895)

```python
container.mount(Label("[bold]Select Nodes to Compare (2+)[/]"))
container.mount(FuzzyCheckList(nodes, item_class="chk_node",
                               placeholder="Type to filter nodes…",
                               id="cmp_nodes"))

container.mount(Label("[bold]Dimensions[/]"))
all_dims = self._get_all_dimension_keys()
if all_dims:
    container.mount(FuzzyCheckList(all_dims, item_class="chk_dim",
                                   default_checked=True,
                                   placeholder="Type to filter dimensions…",
                                   id="cmp_dims"))
else:
    container.mount(Label("[dim]No dimensions found[/]"))
# Target Sections + Next button unchanged.
```

Keep the existing `call_after_refresh(self._refresh_compare_sections)`.

### Auto-focus on step entry

At the end of `_config_hybridize` / `_config_compare`, focus the node list's
filter box: `self.call_after_refresh(lambda: self._focus_fcl_filter("hyb_nodes"))`
(resp. `"cmp_nodes"`). New helper `_focus_fcl_filter(fcl_id)` does
`self.query_one(f"#{fcl_id}", FuzzyCheckList).query_one(Input).focus()` in a
try/except.

### Hint line

In `_actions_show_config`, after `_mount_op_context_header`, for compare /
hybridize mount:
`Label("[dim]↑↓ Navigate  Space Toggle  Tab Switch group  Type to filter[/]")`.

### `on_key` — Tab group cycling + section arrow nav (~line 2858)

Inside the existing `if tabbed.active == "tab_actions" and self._wizard_step > 0:`
block, add (before the current `up/down → _navigate_rows(OperationRow)` branch):

```python
# Compare/Hybridize config step: Tab cycles whole control groups
if (event.key in ("tab", "shift+tab")
        and self._wizard_step == 2
        and self._wizard_op in ("compare", "hybridize")):
    if self._cycle_wizard_groups(-1 if event.key == "shift+tab" else 1):
        event.prevent_default(); event.stop(); return

# Compare config step: ↑/↓ within the section-checkbox group
if (event.key in ("up", "down")
        and self._wizard_step == 2
        and self._wizard_op == "compare"
        and isinstance(self.focused, Checkbox)
        and "chk_section" in self.focused.classes):
    if self._navigate_rows(1 if event.key == "down" else -1,
                           "cmp_sections_box", (Checkbox,)):
        event.prevent_default(); event.stop(); return
```

Arrow nav **inside** a `FuzzyCheckList` is handled by the widget's own
`on_key` (and `event.stop()`), so it never reaches the app handler — no
app-level up/down branch is needed for the node/dimension lists.

### New helper: `_cycle_wizard_groups(direction)`

Builds the ordered list of group "entry widgets" and their membership
containers, finds which group currently holds focus, and focuses the
next/previous group's entry widget (wrapping):

- **Hybridize:** `[#hyb_nodes filter Input]`, `[merge-rules TextArea]`,
  `[.btn_actions_next Button]`.
- **Compare:** `[#cmp_nodes filter Input]`, `[#cmp_dims filter Input]` (omit
  if no dimensions), `[first .chk_section checkbox in #cmp_sections_box]`
  (omit if none yet), `[.btn_actions_next Button]`.

Membership test: focus belongs to a group if `self.focused` is the group
container or the container is in `self.focused.ancestors` (the `FuzzyCheckList`
for list groups; `#cmp_sections_box` for the section group; the widget itself
for `TextArea`/`Button`). On focus, call `.focus()` + `.scroll_visible()`.

## Why existing collection code is untouched

- `_actions_collect_config` (compare & hybridize branches) does
  `container.query("Checkbox.chk_node" / ".chk_dim")` — a **recursive** query,
  so it still finds the checkboxes now nested inside `FuzzyCheckList`. It reads
  `.value`, unaffected by `.display` ⇒ checked-but-filtered rows are still
  collected (the clarified view-only behaviour). **No change.**
- `_refresh_compare_sections` does `self.query("Checkbox.chk_node")` — same.
  **No change.**
- `_on_cmp_node_changed` (`@on(Checkbox.Changed, ".chk_node")`) still fires;
  `chk_dim` toggles do not match its selector. **No change.**
- `_config_hybridize`'s `container.query_one(TextArea)` still resolves to the
  single merge-rules `TextArea` (an `Input` is not a `TextArea`). **No change.**

### CSS (in the `/* Actions wizard */` block, ~line 2050)

```css
FuzzyCheckList { height: auto; margin-bottom: 1; }
FuzzyCheckList .fcl_filter { margin: 0 1; }
FuzzyCheckList .fcl_list { height: auto; max-height: 10; padding: 0 1; }
```

## Verification

1. **Unit test (new):** `python tests/test_brainstorm_wizard_filter.py` —
   covers `_filter_labels`: blank query keeps all, case-insensitive substring
   match, non-match dropped, order preserved, no-match → empty list. Follows
   the pure-helper test pattern of `tests/test_brainstorm_compare_modal.py`.
2. **Import / regression:** run existing brainstorm Python tests to confirm no
   import breakage —
   `python tests/test_brainstorm_wizard_sections.py`,
   `python tests/test_brainstorm_compare_modal.py`,
   `python tests/test_brainstorm_dag_click_focus.py`.
3. **Build verify:** Step 9 runs `verify_build` from
   `aitasks/metadata/project_config.yaml` if configured.
4. **Manual (TUI) — covered by a manual-verification follow-up offered at
   Step 8c:** in `ait brainstorm <task>`, Actions tab →
   - *Hybridize* config step: type in the filter (list narrows live); `↑`/`↓`
     move focus between the filter box and visible nodes; `Space` toggles; a
     checked node filtered out stays checked on the confirm step; `Tab` cycles
     node list → merge-rules → Next.
   - *Compare* config step: node filter and dimension filter both narrow live;
     `↑`/`↓` navigate within the focused list; `Tab`/`Shift+Tab` cycle node
     list → dimension list → section checkboxes → Next → wrap.

## Step 9 — Post-Implementation

Standard cleanup: commit code (`bug:` prefix, `(t806)` suffix) and the plan
file separately, archive via `./.aitask-scripts/aitask_archive.sh 806`, push.
No worktree (current-branch workflow). No skill/template changes ⇒ no
Codex/Gemini/OpenCode port and no `aitask_skill_verify.sh` run needed.
