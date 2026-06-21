---
Task: t1018_3_double_click_open_detail.md
Parent Task: aitasks/t1018_brainstorm_op_restart_dblclick_footer_hygiene.md
Sibling Tasks: aitasks/t1018/t1018_*.md
Archived Sibling Plans: aiplans/archived/p1018/p1018_*_*.md
Worktree: (current branch — profile 'fast')
Branch: main
Base branch: main
---

# p1018_3 — Double-click to open operation/node detail

Independent child of t1018 (no sibling dependency). Adds double-click → open
detail on Browse node rows / DAG nodes / Running-tab operation rows, mirroring
the only existing `event.chain == 2` pattern in the codebase.

## Verified current state (read before coding — confirm line numbers)

- **Detail screens / messages:** `OperationDetailScreen` (`brainstorm_app.py:1601`)
  pushed via `OperationOpened` from `NodeRow.action_open_operation`
  (`:2553-2574`, bound `o` at `:2522-2524`; App handler `:8062-8069`) and from
  `DAGDisplay.action_open_operation` (`brainstorm_dag_display.py:816`; App handler
  `brainstorm_app.py:8007-8014`).
- **Enter vs o diverge:** NodeRow `Enter` → `action_open_node_detail`
  (`:6024-6040`) opens the **NodeHub** modal (offers Operations/Compare);
  NodeRow `o` → OperationDetailScreen. GroupRow `Enter` only expand/collapses
  (`:5838-5847`). StatusLogRow `Enter` → LogDetailModal (`:5848-5852`).
- **Click handlers today:** `NodeRow` has **no `on_click`** (default Static focus).
  `OperationRow.on_click` (`:2808-2812`) posts `Activated` (single-click only, no
  `chain`; used in wizard/session lists — leave unchanged).
  `DAGDisplay._handle_click` (`brainstorm_dag_display.py:675-705`) single-click
  focuses a node + posts `FocusChanged`; `_DAGStatic.on_click` forwards x/y
  (`:456-460`).
- **Reference pattern (mirror this):** `board/aitask_board.py:1263-1273`
  (`TaskCard.on_click`): `event.chain == 2` → expand; else open details.

## Per-surface behavior (recommended; confirm in-task)
- **Browse NodeRow / DAG node** → double-click opens the **NodeHub** (matches the
  primary `Enter` detail entry).
- **Running-tab GroupRow** → double-click opens the **OperationDetailScreen** (the
  detail `Enter` does NOT open — `Enter` only expand/collapses).
- Single-click semantics (focus / expand-collapse) unchanged everywhere.

## Implementation steps

### Step 1 — NodeRow double-click
Add `def on_click(self, event)` to `NodeRow`: if `event.chain == 2`, post the
same message `Enter` triggers so the App opens the NodeHub (reuse the existing
`action_open_node_detail` path / its message — do not duplicate the push). Else
fall through to default focus. Follow `TaskCard.on_click` shape.

### Step 2 — GroupRow double-click
Add `on_click` to `GroupRow` (`:3115-3150`): `event.chain == 2` → post
`OperationOpened` (or directly open `OperationDetailScreen`) for
`group_info["operation"]`; else preserve single-click focus and keep the
`Enter`-driven expand/collapse intact.

### Step 3 — DAG node double-click
In `DAGDisplay._handle_click` (`:675-705`), after resolving the clicked node box,
branch on `event.chain == 2` → post the detail-open message (same as NodeRow
double-click); `chain == 1` keeps the existing focus + `FocusChanged`. Confirm
`_DAGStatic.on_click` (`:456-460`) forwards `event.chain` (Textual `Click`
carries it) — thread it through if the forwarder constructs a new event.

### Step 4 — Leave OperationRow single-click unchanged
`OperationRow.on_click` (`:2808-2812`) is used in wizard/session-lifecycle lists,
not Browse — out of scope.

## Risk
### Code-health risk: low
- Adding `on_click` handlers is additive; main risk is intercepting single-click
  focus. · mitigation: explicit `chain == 1` fall-through + pilot tests.
### Goal-achievement risk: low
- Headless synthetic `Click` events don't exercise real terminal→tmux mouse
  delivery. · mitigation: live mouse check in t1018_4.

## Verification
- Tests: construct a Textual `Click` with `chain == 2` on NodeRow / GroupRow /
  DAG node → assert the correct screen/modal pushed; `chain == 1` preserves
  focus/expand. Mirror any board double-click test.
- Full brainstorm suite green.
- Live mouse double-click through real tmux — covered by t1018_4.

## Step 9 — Post-implementation
Archive via `./.aitask-scripts/aitask_archive.sh 1018_3`. Parent stays active
until siblings + t1018_4 land.
