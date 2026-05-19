---
Task: t797_disallow_patch_for_node_without_plan.md
Base branch: main
plan_verified: []
---

# t797 — Disallow patch op for nodes without a plan + universal plan indicator

## Context

In `ait brainstorm` (the Textual TUI under `.aitask-scripts/brainstorm/`), the
"patch" operation in the Actions wizard modifies a node's existing
implementation plan. Today the wizard lets the user pick *any* node as the
patch target, including nodes that have never had a plan generated (e.g.,
nodes created by the Initializer or by Explore ops). The downstream agent
input assembly (`_assemble_input_patcher` in `brainstorm_crew.py:415`)
silently omits the plan path when no plan file exists, so the patcher
either no-ops or produces incorrect output — a confusing failure mode.

Additionally, none of the three places that render nodes (Dashboard
NodeRow, Graph DAG box, Actions tab OperationRow) currently signal which
nodes have a plan. Users have no way to tell at a glance which nodes are
valid patch targets, or which are far enough along in the design loop to
finalize.

This task does two things:

1. **Block patch op on plan-less nodes** in the Actions wizard Step 2, with
   a meaningful disabled-row affordance plus a defensive guard on the Next
   button.
2. **Add a single-character "has plan" indicator (●, green)** to all three
   node-rendering surfaces, so users see plan status uniformly.

User decisions captured before planning:
- Add the indicator in **all three** places (Dashboard, Graph, Actions).
- For plan-less rows in Actions patch step, show **"(no plan — patch
  unavailable)"** suffix alongside the disabled/strikethrough rendering.
- Indicator is a single character where space is constrained (graph box).

## Files to modify

1. `.aitask-scripts/brainstorm/brainstorm_app.py`
2. `.aitask-scripts/brainstorm/brainstorm_dag_display.py`

No other files need changes. Plan-existence semantics are already canonical
(YAML `plan_file` field on the node, set by `update_node` in
`brainstorm_session.py:732` after the patcher/detailer writes a plan).

## Indicator design

Two states are signalled, both with a single-character symbol and (where
space allows) an explanatory label:

| State    | Symbol      | Label       | Style                                |
|----------|-------------|-------------|--------------------------------------|
| has plan | `●`         | `has plan`  | green + bold (matches `HEAD_TAG_STYLE`) |
| no plan  | `○`         | `no plan`   | dim                                  |

- Both states are rendered (not just "has plan") so the user always sees
  per-node state, and the label after the symbol acts as a legend that
  explains what `●` / `○` mean.
- **Where space allows** (Dashboard NodeRow, Actions tab OperationRow):
  show `<symbol> <label>` after the node id (and any HEAD tag).
- **Where space is constrained** (Graph DAG box, inner width = 26): show
  only the symbol after the node id / HEAD tag. The Dashboard and
  Actions-tab labels visible in the same TUI session act as the legend
  that explains the symbol shown in the graph.
- For the patch op's disabled rows, the existing "(no plan — patch
  unavailable)" suffix supplies the *reason*; the `○ no plan` indicator
  in the label still appears for consistency with non-patch rows.

Semantics used everywhere: `bool(node_data.get("plan_file"))`.
The YAML's `plan_file` field is authoritative — it's set when a plan is
written and read by `finalize_session` (`brainstorm_session.py:308-311`).

## Implementation steps

### Step 1 — Add `_node_has_plan` helper on `BrainstormApp`

File: `.aitask-scripts/brainstorm/brainstorm_app.py`

Add a small helper method on the `BrainstormApp` class so both the
Dashboard population and the Actions wizard share the same check. Place it
near the other `_node_*` helpers (e.g. next to `_node_sections` /
`_node_has_sections`).

```python
def _node_has_plan(self, node_id: str) -> bool:
    """Return True if the node has a plan_file set in its YAML."""
    try:
        data = read_node(self.session_path, node_id)
    except Exception:
        return False
    return bool(data.get("plan_file"))
```

### Step 2 — NodeRow (Dashboard tab) shows the indicator

File: `.aitask-scripts/brainstorm/brainstorm_app.py`

**At `NodeRow.__init__` (line 1584):** add a `has_plan: bool = False`
parameter and store it.

**At `NodeRow.render` (line 1591-1593):** append the indicator after the
HEAD marker.

```python
def __init__(self, node_id: str, description: str, is_head: bool = False,
             has_plan: bool = False):
    super().__init__()
    self.node_id = node_id
    self.node_description = description
    self.is_head = is_head
    self.has_plan = has_plan
    self.can_focus = True

def render(self) -> str:
    head_marker = " [bold green]HEAD[/]" if self.is_head else ""
    plan_marker = (
        " [bold green]● has plan[/]" if self.has_plan
        else " [dim]○ no plan[/]"
    )
    return f"[bold]{self.node_id}[/]{head_marker}{plan_marker}  {self.node_description}"
```

**At `_populate_node_list` (line 4089-4093):** pass `has_plan` through.

```python
for nid in nodes:
    node_data = read_node(self.session_path, nid)
    desc = node_data.get("description", "")
    has_plan = bool(node_data.get("plan_file"))
    row = NodeRow(nid, desc, is_head=(nid == head), has_plan=has_plan)
    pane.mount(row)
```

(Reuses `node_data` already fetched — no extra disk I/O.)

### Step 3 — Graph DAG box shows the indicator

File: `.aitask-scripts/brainstorm/brainstorm_dag_display.py`

**At `_build_graph` (line 71-107):** extend the returned tuple with a
`node_has_plan_map: dict[str, bool]`.

```python
def _build_graph(
    session_path: Path,
) -> tuple[list[str], dict, dict, dict, dict, dict]:
    ...
    node_op_map: dict[str, str] = {}
    node_has_plan_map: dict[str, bool] = {}
    ...
    for nid in nodes:
        data = read_node(session_path, nid)
        ...
        node_op_map[nid] = op
        node_has_plan_map[nid] = bool(data.get("plan_file"))
        ...
    return nodes, parent_map, child_map, node_descs, node_op_map, node_has_plan_map
```

**At the caller (line 523, 529):** unpack the new map and store it.

```python
nodes, parent_map, child_map, node_descs, node_op_map, node_has_plan_map = _build_graph(...)
...
self._node_op_map = node_op_map
self._node_has_plan_map = node_has_plan_map
```

Also initialize `self._node_has_plan_map: dict[str, bool] = {}` next to
`self._node_op_map` at line 510.

**Thread it through `_render_layer` → `_render_node_box`:**

- `_render_layer` (line 278-): add `node_has_plan_map: dict[str, bool] |
  None = None` param, default `{}`; pass `has_plan=plan_map.get(nid,
  False)` to `_render_node_box`.
- `_render_node_box` (line 194-): add `has_plan: bool = False` param.

**In `_render_node_box` row 1 (the title row, line 235-246):** append the
indicator symbol after the optional ` HEAD` tag. Only the symbol fits
here — labels are omitted to preserve box width.

```python
inner.append(node_id, style=NODE_ID_STYLE + bg)
if is_head:
    inner.append(" HEAD", style=HEAD_TAG_STYLE + bg)
if has_plan:
    inner.append(" ●", style=HEAD_TAG_STYLE + bg)
else:
    inner.append(" ○", style=Style(dim=True) + bg)
```

Inner width is 26; typical `node_id` (4-6 chars) + " HEAD" + " ○|●" fits
comfortably. The existing `pad = inner_w - len(inner.plain)` clause
handles overflow protection.

The symbol-only rendering here is the space-constrained variant; the
explanatory `has plan` / `no plan` labels rendered on the Dashboard and
Actions tab serve as the legend that explains what these symbols mean.

**At the `_render_layer` call site (line 581-):** pass
`node_has_plan_map=self._node_has_plan_map`.

### Step 4 — OperationRow indicator + patch-op disabling

File: `.aitask-scripts/brainstorm/brainstorm_app.py`

`OperationRow` (line 1678-1708) already supports `disabled=True` (renders
as `[dim strikethrough]…[/]`, sets `can_focus = False`, ignores clicks).
Reuse it — no class changes needed for the disable path.

**At `_actions_show_node_select` (line 4602-4646):** when building rows,
compute plan status per node and:

- Append the `●` indicator into the rendered label for **all** node-select
  ops (explore / detail / patch) when the node has a plan
- For `_wizard_op == "patch"` *and* the node has no plan: pass
  `disabled=True` and append `(no plan — patch unavailable)` to the
  description

Replace lines 4637-4641 with:

```python
for nid in nodes:
    node_data = read_node(self.session_path, nid)
    desc = node_data.get("description", "")
    has_plan = bool(node_data.get("plan_file"))

    lbl_parts = [nid]
    if nid == head:
        lbl_parts.append("[green]HEAD[/]")
    if has_plan:
        lbl_parts.append("[bold green]● has plan[/]")
    else:
        lbl_parts.append("[dim]○ no plan[/]")
    lbl = " ".join(lbl_parts)

    disabled = (self._wizard_op == "patch" and not has_plan)
    if disabled:
        desc = f"{desc}  [italic](patch unavailable)[/]"

    container.mount(OperationRow(nid, lbl, desc, disabled=disabled))
```

Note: `OperationRow.render` already wraps the whole description in `[dim]`
when disabled, so the italic suffix is dimmed automatically. The phrase
shortens from "(no plan — patch unavailable)" to "(patch unavailable)"
because the leading `○ no plan` label already states the no-plan
condition — repeating it would be redundant.

### Step 5 — Defensive Next-button guard

File: `.aitask-scripts/brainstorm/brainstorm_app.py`

`OperationRow` already prevents clicks/focus on disabled rows, so the
selection flow can't ordinarily land on a plan-less node for patch. But
add a belt-and-braces guard in `_on_actions_next` so any future refactor
that bypasses the row-disable doesn't regress the bug.

**At `_on_actions_next` after line 5067 (where `node` is fetched):**

```python
node = self._wizard_config.get("_selected_node")
if not node:
    self.notify("Select a node first", severity="warning")
    return
if self._wizard_op == "patch" and not self._node_has_plan(node):
    self.notify(
        f"Node '{node}' has no plan — patch is only valid on nodes that "
        f"already have an implementation plan.",
        severity="error",
        timeout=6,
    )
    return
```

This message is the "meaningful error" the task asks for. It fires only
if the disabled-row affordance somehow fails — the primary UX remains the
greyed-out row + suffix.

## Step 9: Post-Implementation

Standard archival, plan-file consolidation, and merge per the
task-workflow Step 9.

## Verification

This is a TUI change — type-check verifies code correctness, but feature
correctness requires manual interaction. Plan to do **both**.

### Static checks

```bash
# Syntax / import check
python -c "import ast; ast.parse(open('.aitask-scripts/brainstorm/brainstorm_app.py').read())"
python -c "import ast; ast.parse(open('.aitask-scripts/brainstorm/brainstorm_dag_display.py').read())"

# Run any brainstorm-related unit tests
for t in tests/test_brainstorm*.sh; do
    [ -f "$t" ] && bash "$t"
done
```

### Manual smoke (load a real session)

1. `./ait brainstorm` on a task that has an existing brainstorm session with
   a mix of plan-having and plan-less nodes (e.g. a session where Detail or
   Patch has been run on some nodes but not others).
2. **Dashboard tab:** confirm each node row shows `● has plan` (green)
   when the node has a `plan_file`, and `○ no plan` (dim) when it doesn't.
3. **Graph tab:** confirm the title row of each DAG box ends with `●`
   (green) for plan-having nodes and `○` (dim) for plan-less nodes
   (symbol only, no label, due to box width). Confirm `HEAD` tag and the
   plan symbol coexist when both apply.
4. **Actions tab → Patch:**
   - Step 1: pick "Patch".
   - Step 2: confirm plan-less nodes show `○ no plan` in the label and
     are rendered with strikethrough + `(patch unavailable)` and cannot
     be focused or clicked. Plan-having nodes show `● has plan` (green)
     and are selectable.
   - Try keyboard arrows: focus skips disabled rows.
   - Try clicking a disabled row: nothing happens.
5. **Actions tab → Explore / Detail (regression):** confirm the `● has
   plan` / `○ no plan` indicator is present but NO disabling — every
   node is still selectable.
6. **Edge cases:**
   - Session with all plan-less nodes → patch step 2 shows all rows
     disabled, Next button stays disabled, user is forced to back out.
   - Session with all plan-having nodes → no rows disabled, indicator on
     every row.

### Defensive guard

To verify the Next-button guard: temporarily comment out the `disabled=`
in step 4 (do not commit), pick a plan-less node for patch, click Next,
and confirm the error notify fires. Restore the disable before final
commit.

## Notes for archival

- Update plan file with `## Final Implementation Notes` and the
  `Upstream defects identified` canonical bullet (likely `None` here — the
  existing `_assemble_input_patcher` "silent omit when no plan" behavior is
  *related* but acceptable as a defensive fallback now that the UI blocks
  patch dispatch upstream).
- Commit message: `bug: Block patch op on plan-less nodes; show plan
  indicator everywhere (t797)`.
