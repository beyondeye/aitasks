---
Task: t464_keyboard_shortcuts_in_brainstormtui.md
Worktree: (current branch)
Branch: main
Base branch: main
---

# Plan: t464 — Keyboard Shortcuts in Brainstorm TUI

## Context
The brainstorm TUI (`brainstorm_app.py`) lacks visible tab-switching keyboard shortcuts, has no arrow-key navigation in the Actions wizard and Status tab, doesn't show Esc-back hints in wizard steps, and mixes node selection with config in wizard step 2. This task adds these UX improvements.

**File to modify:** `.aitask-scripts/brainstorm/brainstorm_app.py`

---

## Change 1: Tab Shortcuts with Letters in Footer + Rename DAG to Graph

Replace number-based `_TAB_SHORTCUTS` dict (lines 99-105) with letter-based BINDINGS. Rename "DAG" tab label to "Graph".

Shortcuts: **d**=Dashboard, **g**=Graph, **c**=Compare, **a**=Actions, **s**=Status

### Conflict resolution
- `c` is currently used in `on_key` for compare-select (only on Compare tab, line 931). Move this logic into `action_tab_compare` — if already on Compare tab, trigger compare select.
- `d` is currently used for diff in Compare tab (line 945). Since `d` is now Dashboard, change diff shortcut to `D` (shift+d) in `on_key`.

### Steps

1. **Delete `_TAB_SHORTCUTS` dict** (lines 99-105)

2. **Expand BINDINGS** (lines 837-839):
```python
BINDINGS = [
    Binding("q", "quit", "Quit"),
    Binding("d", "tab_dashboard", "Dashboard"),
    Binding("g", "tab_graph", "Graph"),
    Binding("c", "tab_compare", "Compare"),
    Binding("a", "tab_actions", "Actions"),
    Binding("s", "tab_status", "Status"),
]
```

3. **Add action methods** for each tab:
```python
def action_tab_dashboard(self) -> None:
    if isinstance(self.screen, ModalScreen):
        return
    self.query_one(TabbedContent).active = "tab_dashboard"

def action_tab_graph(self) -> None:
    if isinstance(self.screen, ModalScreen):
        return
    self.query_one(TabbedContent).active = "tab_dag"

def action_tab_compare(self) -> None:
    if isinstance(self.screen, ModalScreen):
        return
    tabbed = self.query_one(TabbedContent)
    if tabbed.active == "tab_compare":
        # Already on compare — trigger compare node select
        nodes = list_nodes(self.session_path)
        if len(nodes) < 2:
            self.notify("Need at least 2 nodes to compare", severity="warning")
        else:
            self.push_screen(CompareNodeSelectModal(nodes), callback=self._on_compare_selected)
        return
    tabbed.active = "tab_compare"

def action_tab_actions(self) -> None:
    if isinstance(self.screen, ModalScreen):
        return
    self.query_one(TabbedContent).active = "tab_actions"

def action_tab_status(self) -> None:
    if isinstance(self.screen, ModalScreen):
        return
    self.query_one(TabbedContent).active = "tab_status"
```

4. **Rename "DAG" to "Graph"** in `compose()` (line 866):
```python
with TabPane("Graph", id="tab_dag"):
```

5. **Remove from `on_key`:**
   - Delete `c` handler (lines 931-943) — moved to `action_tab_compare`
   - Change `d` handler (line 945) to `D` for diff
   - Delete `_TAB_SHORTCUTS` handler at bottom (lines 985-990)

---

## Change 2: Up/Down Arrow Navigation in Actions Wizard

Add up/down key handling in `on_key` for the Actions tab to cycle focus between OperationRow widgets.

### Steps

Add to `on_key`, inside the `tab_actions` wizard block (after line 908):

```python
if event.key in ("up", "down") and self._wizard_step in (1, 2):
    focused = self.focused
    if isinstance(focused, OperationRow):
        container = self.query_one("#actions_content", VerticalScroll)
        rows = [w for w in container.query(OperationRow) if not w.op_disabled]
        if rows:
            try:
                idx = rows.index(focused)
            except ValueError:
                idx = 0
            if event.key == "down":
                idx = (idx + 1) % len(rows)
            else:
                idx = (idx - 1) % len(rows)
            rows[idx].focus()
            rows[idx].scroll_visible()
            event.prevent_default()
            event.stop()
            return
```

---

## Change 3: Esc-back Hint in Wizard Steps

All step indicators for steps > 1 include "(Esc: Back)". Implemented as part of Change 4 step indicator labels.

---

## Change 4: Dedicated Node Selection Step for explore/detail/patch

Restructure wizard so node-based operations have a dedicated node selection step:

| Operation | Step 1 | Step 2 | Step 3 | Step 4 |
|-----------|--------|--------|--------|--------|
| explore | Op select | Node select | Config (mandate+parallel) | Confirm |
| detail | Op select | Node select | Confirm | — |
| patch | Op select | Node select | Config (patch request) | Confirm |
| compare | Op select | Config (nodes+dims) | Confirm | — |
| hybridize | Op select | Config (nodes+rules) | Confirm | — |
| session ops | Op select | → Confirm | — | — |

### Steps

1. **Add `_wizard_total_steps` instance variable** (line 847):
```python
self._wizard_total_steps: int = 3
```

2. **Add `_set_total_steps` helper**:
```python
def _set_total_steps(self) -> None:
    if self._wizard_op in ("explore", "patch"):
        self._wizard_total_steps = 4
    else:
        self._wizard_total_steps = 3
```

3. **Add `selected` reactive to OperationRow** (line 391) for visual node selection feedback:
```python
from textual.reactive import reactive
# Add to OperationRow class:
selected = reactive(False)

def render(self) -> str:
    if self.op_disabled:
        return f"[dim strikethrough]{self.op_label}[/]  [dim]{self.op_description}[/]"
    marker = "[bold cyan]> [/]" if self.selected else "  "
    return f"{marker}[bold]{self.op_label}[/]  {self.op_description}"
```

4. **Add `_actions_show_node_select` method** (new dedicated node selection step):
```python
def _actions_show_node_select(self) -> None:
    """Step 2: dedicated node selection for explore/detail/patch."""
    self._wizard_step = 2
    self._wizard_config = {}
    container = self.query_one("#actions_content", VerticalScroll)
    container.remove_children()

    total = self._wizard_total_steps
    desc_map = {"explore": "Select Base Node", "detail": "Select Node", "patch": "Select Node to Patch"}
    container.mount(Label(
        f"Step 2 of {total} — {desc_map.get(self._wizard_op, 'Select Node')}  (Esc: Back)",
        classes="actions_step_indicator",
    ))
    container.mount(Label("[dim]  ↑↓ Navigate  Enter Select  |  Click node + Next[/dim]"))

    nodes = list_nodes(self.session_path)
    head = get_head(self.session_path)
    for nid in nodes:
        node_data = read_node(self.session_path, nid)
        desc = node_data.get("description", "")
        lbl = f"{nid} [green]HEAD[/]" if nid == head else nid
        container.mount(OperationRow(nid, lbl, desc))

    container.mount(Button("Next ▶", variant="primary", classes="btn_actions_next", disabled=True))
    self.call_after_refresh(self._focus_first_operation)
```

5. **Convert `_actions_show_step2` into a router**:
```python
def _actions_show_step2(self) -> None:
    if self._wizard_op in ("explore", "detail", "patch"):
        self._actions_show_node_select()
    else:
        self._actions_show_config()
```

6. **Add `_actions_show_config` method** (config form without node list):
```python
def _actions_show_config(self) -> None:
    op = self._wizard_op
    if op in ("explore", "patch"):
        self._wizard_step = 3
    else:
        self._wizard_step = 2
    container = self.query_one("#actions_content", VerticalScroll)
    container.remove_children()
    total = self._wizard_total_steps
    step = self._wizard_step
    container.mount(Label(
        f"Step {step} of {total} — Configure: {op.title()}  (Esc: Back)",
        classes="actions_step_indicator",
    ))
    if op == "explore":
        self._config_explore_no_node(container)
    elif op == "compare":
        self._config_compare(container)
    elif op == "hybridize":
        self._config_hybridize(container)
    elif op == "patch":
        self._config_patch_no_node(container)
```

7. **Add `_config_explore_no_node` and `_config_patch_no_node`** (config without node list):
```python
def _config_explore_no_node(self, container):
    node_id = self._wizard_config.get("_selected_node", "?")
    container.mount(Label(f"[bold]Base Node:[/] {node_id}"))
    container.mount(Label("[bold]Exploration Mandate[/]"))
    container.mount(TextArea(""))
    container.mount(CycleField("Parallel explorers", ["1", "2", "3", "4"], initial="2"))
    container.mount(Button("Next ▶", variant="primary", classes="btn_actions_next"))

def _config_patch_no_node(self, container):
    node_id = self._wizard_config.get("_selected_node", "?")
    container.mount(Label(f"[bold]Node:[/] {node_id}"))
    container.mount(Label("[bold]Patch Request[/]"))
    container.mount(TextArea(""))
    container.mount(Button("Next ▶", variant="primary", classes="btn_actions_next"))
```

8. **Rename `_actions_show_step3` to `_actions_show_confirm`** and update step indicator:
```python
def _actions_show_confirm(self) -> None:
    total = self._wizard_total_steps
    self._wizard_step = total
    # ... rest same as current _actions_show_step3 but with:
    Label(f"Step {total} of {total} — Confirm  (Esc: Back)", ...)
```

9. **Update Enter key handling in `on_key`** — add handler for step 2 node select (Enter selects + advances):
```python
if event.key == "enter" and self._wizard_step == 2:
    focused = self.focused
    if isinstance(focused, OperationRow) and not focused.op_disabled:
        if self._wizard_op in ("explore", "detail", "patch"):
            self._wizard_config["_selected_node"] = focused.op_key
            if self._wizard_op == "detail":
                self._wizard_config["node"] = focused.op_key
                self._actions_show_confirm()
            else:
                self._actions_show_config()
            event.prevent_default()
            event.stop()
            return
```

10. **Update `on_descendant_focus`** to enable Next button and set selected visual when focusing a node in step 2:
```python
if isinstance(event.widget, OperationRow):
    tabbed = self.query_one(TabbedContent)
    if tabbed.active == "tab_actions" and self._wizard_step == 2:
        if self._wizard_op in ("explore", "detail", "patch"):
            self._wizard_config["_selected_node"] = event.widget.op_key
            container = self.query_one("#actions_content", VerticalScroll)
            for row in container.query(OperationRow):
                row.selected = (row.op_key == event.widget.op_key)
            try:
                self.query_one(".btn_actions_next", Button).disabled = False
            except Exception:
                pass
```

11. **Update `on_operation_row_activated`** for mouse clicks: add `_set_total_steps()` call, handle step 2 node selection with visual feedback + enable Next.

12. **Update Esc-back navigation** (lines 889-896):
```python
if event.key == "escape" and self._wizard_step > 1:
    if self._wizard_step == self._wizard_total_steps:
        if self._wizard_op in ("explore", "patch"):
            self._actions_show_config()
        elif self._wizard_op == "detail":
            self._actions_show_node_select()
        else:
            self._actions_show_config()
    elif self._wizard_step == 3 and self._wizard_op in ("explore", "patch"):
        self._actions_show_node_select()
    elif self._wizard_step == 2:
        self._actions_show_step1()
    event.prevent_default()
    event.stop()
    return
```

13. **Update `_on_actions_next` button handler**:
```python
def _on_actions_next(self) -> None:
    if self._wizard_step == 2:
        if self._wizard_op in ("explore", "detail", "patch"):
            node = self._wizard_config.get("_selected_node")
            if not node:
                self.notify("Select a node first", severity="warning")
                return
            if self._wizard_op == "detail":
                self._wizard_config["node"] = node
                self._actions_show_confirm()
            else:
                self._actions_show_config()
        elif self._actions_collect_config():
            self._actions_show_confirm()
    elif self._wizard_step == 3 and self._wizard_op in ("explore", "patch"):
        if self._actions_collect_config():
            self._actions_show_confirm()
```

14. **Update `_on_actions_back` button handler**:
```python
def _on_actions_back(self) -> None:
    if self._wizard_op in ("explore", "patch"):
        self._actions_show_config()
    elif self._wizard_op == "detail":
        self._actions_show_node_select()
    else:
        self._actions_show_config()
```

15. **Update `_actions_collect_config`**: Preserve `_selected_node` from step 2. The node is already in `_wizard_config` so just don't overwrite it.

---

## Change 5: Up/Down Arrow Navigation in Status Tab

Add to `on_key`, when Status tab is active:

```python
if event.key in ("up", "down"):
    tabbed = self.query_one(TabbedContent)
    if tabbed.active == "tab_status":
        focused = self.focused
        if isinstance(focused, (GroupRow, AgentStatusRow, StatusLogRow)):
            container = self.query_one("#status_content", VerticalScroll)
            focusable = [
                w for w in container.children
                if isinstance(w, (GroupRow, AgentStatusRow, StatusLogRow))
            ]
            if focusable:
                try:
                    idx = focusable.index(focused)
                except ValueError:
                    idx = 0
                idx = (idx + 1) % len(focusable) if event.key == "down" else (idx - 1) % len(focusable)
                focusable[idx].focus()
                focusable[idx].scroll_visible()
                event.prevent_default()
                event.stop()
                return
```

---

## Verification

1. Launch `./ait brainstorm tui <task_num>` (requires active brainstorm session)
2. Footer shows: d=Dashboard, g=Graph, c=Compare, a=Actions, s=Status
3. Press letter keys to switch tabs; "DAG" tab shows as "Graph"
4. Press `c` twice: first switches to Compare, second opens compare select
5. On Compare tab, `D` (shift) triggers diff (was `d`)
6. Actions tab step 1: up/down arrows navigate between operations, Enter selects
7. After selecting explore/detail/patch: dedicated node selection step with instructions
8. In node select: up/down navigates, Enter selects and advances, click + Next also works
9. Next button disabled until node selected; selected node shows `>` marker
10. Esc goes back at every wizard step > 1; step indicators show "(Esc: Back)"
11. Status tab: up/down navigates between GroupRow/AgentStatusRow/StatusLogRow

## Final Implementation Notes
- **Actual work done:** All 5 changes implemented as planned in `brainstorm_app.py`. Tab shortcuts use letters (d/g/c/a/s) shown in Footer via BINDINGS. DAG renamed to Graph. Wizard restructured with dedicated node selection step for explore/detail/patch. Up/down arrow navigation added for Actions wizard and Status tab. Esc-back hints added to all wizard steps > 1.
- **Deviations from plan:** None significant. The implementation closely followed the plan.
- **Issues encountered:** None.
- **Key decisions:** `c` on Compare tab doubles as compare-select (moved from `on_key` to `action_tab_compare`). Diff shortcut changed from `d` to `D` to avoid Dashboard conflict. Step 1 indicator omits total count since it varies by operation.

## Step 9 (Post-Implementation)
Archive task, commit, and push per aitask workflow.
