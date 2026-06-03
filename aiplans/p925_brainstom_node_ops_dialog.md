---
Task: t925_brainstom_node_ops_dialog.md
Worktree: (current branch — profile 'fast')
Branch: main
Base branch: main
---

# t925 — Brainstorm node-op dialog: full op surface, clearer shortcut, delete node

## Context

In `ait brainstorm`, focusing a DAG node on the Dashboard/Graph tabs and pressing
`A` opens `NodeActionSelectModal` to pick an operation to run on that node. Three
problems have accumulated:

1. **Stale op list.** The dialog hardcodes `_OPS = ["explore", "detail", "patch",
   "fast_track"]` (`brainstorm_app.py:2051`). Since module operations
   (`module_decompose`, `module_merge`, `module_sync`) were introduced they are
   reachable only via the separate subgraph-select wizard, so the node dialog no
   longer reflects all available operations.
2. **Unintuitive shortcut.** `A` is labelled "Node op" but reads as "Actions"
   (the lowercase `a` switches to the "(A)ctions" tab, and the op jumps into that
   tab's wizard), confusing users.
3. **No node delete.** There is no way to delete a node and its descendants; only
   a session-level `delete` exists.

**Outcome:** the node dialog surfaces *every* applicable operation (relevance-
filtered, disabled-with-reason when not), the `A` shortcut is relabelled, and a
new cascade **delete** operation is added with HEAD repointing and safety guards.

Product decisions confirmed with the user:
- Surface all ops, **relevance-filtered** (shown disabled + reason when N/A).
- **Keep the `A` key**, relabel "Node op" → **"Node action"**.
- Delete **cascades to all descendants + resets HEAD**; confirm modal lists every
  casualty.
- Delete **blocks on running agents**, **warns (does not block) on linked aitasks**
  (the aitask itself is left untouched).

## Approach

All changes live in `.aitask-scripts/brainstorm/`. Core graph mutation goes into
the **pure, unit-testable** `brainstorm_dag.py`; the TUI in `brainstorm_app.py`
stays a thin renderer/router that reuses existing patterns (the `fast_track`
node→module seeding, the `DeleteSessionModal` double-confirm, and the verified
`_recover_node_id_from_input` agent→node parser).

### 1. `brainstorm_dag.py` — closure + cascade delete (pure helpers)

Add three module-level functions (after `get_children`, ~line 222; `deque` is
already imported at line 14):

- `node_descendants_closure(session_path, node_id) -> list[str]` — BFS over
  `get_children` returning `node_id` plus all transitive descendants. Shared by
  the modal (for the casualty list / guard) and `delete_node_cascade`.
- `_first_surviving_parent(session_path, node_id, closure) -> str | None` —
  climbs `get_parents`, skipping closure members, returns the first survivor or
  `None`. Module-private.
- `delete_node_cascade(session_path, node_id) -> dict` — the executor. Algorithm:
  1. If `node_id` not in `list_nodes`, return `{"deleted": [], "head_repoints": {},
     "history_pruned": {}, "missing_root": True}`.
  2. Compute `closure = node_descendants_closure(...)`. Snapshot each node's
     `plan_file` field **before** deleting (stash `{nid: plan_rel}`).
  3. Read graph state once (`_read_graph_state`). For each module HEAD in
     `current_heads` **and** the legacy `_umbrella` via `current_head`: if that
     head ∈ closure, repoint to `_first_surviving_parent(<focused root>, closure)`
     (or `None`). Mirror `_umbrella` → legacy `current_head` exactly like
     `set_head` (dag.py:172-178). Record `head_repoints[module]`.
  4. Prune every closure id from each per-module `history` list (legacy list →
     treat as `{_umbrella: list}`). Record `history_pruned[module]`. **Leave
     `module_tasks`, `last_synced_at`, `module_deferred` untouched** (linked
     aitask preserved).
  5. `_write_graph_state(...)`, then delete files (best-effort `missing_ok=True`):
     `br_nodes/<id>.yaml`, `br_proposals/<id>.md`, `br_plans/<id>_plan.md`, and
     the stashed `plan_file` if it differs.
  6. Return the report dict.

  **Multi-parent note (document in docstring):** closure is child-transitive, so a
  `synthesize`/`module_merge` node outside the subtree that lists an affected node
  among several parents is pulled into the closure (intentional over-delete) — no
  dangling parent refs are produced. The confirm modal shows the full closure.

### 2. `brainstorm_app.py` — dialog, routing, binding, delete UI

- **Relevance map (extract a testable method).** Add
  `_node_action_op_states(self, node_id) -> dict[str, tuple[bool, str]]` that reads
  `module = _node_module(...)`, `is_umbrella`, `module_tasks` (linked?),
  `source_head = get_head(module=module)`, `ancestors =
  _ancestor_subgraphs(source_head)` and returns disabled+reason per op:
  - `patch`: `(not has_plan, "node has no plan")`
  - `module_decompose`: `(is_umbrella, "no module on the root design")`
  - `module_merge`: disabled if `is_umbrella or not ancestors` (reason varies)
  - `module_sync`: disabled if `is_umbrella or not linked_task` (reason varies)
  `explore`/`detail`/`fast_track`/`delete` default enabled.
- **`action_node_action` (3589):** after computing `has_plan`, call
  `_node_action_op_states(node_id)` and pass the result into the modal.
- **`NodeActionSelectModal` (2033):** expand `_OPS` to include
  `module_decompose, module_merge, module_sync, delete`; add a `delete` entry to
  `_LOCAL_LABELS` ("Delete this node" / "Remove this node and all its
  descendants"); add constructor arg `op_states: dict | None = None` (default
  `{}` so existing test call sites keep working); in `compose`, replace the inline
  patch-disable with `disabled, reason = self.op_states.get(op_key, (False, ""))`
  and append `(reason)` to the description. Reword the docstring + title/hint copy
  so they no longer imply only three ops.
- **`_on_node_action_result` (3670):** after the `fast_track` block, add routing:
  - `delete` → `self._open_delete_node_modal(node_id)`.
  - `module_decompose|module_merge|module_sync` → mirror the `fast_track` seeding
    *without* `_wizard_fast_track`: set `_wizard_op`, `_set_total_steps()`, then
    `_wizard_subgraph = _node_module(node_id)`, `_wizard_config = {}`,
    `_actions_show_config()`, `call_after_refresh(_enter_actions_tab)`.
- **`DeleteNodeModal(ModalScreen)`** (model on `DeleteSessionModal`, ~702): lists
  **every** closure id; shows a yellow warning per affected module with a linked
  `module_tasks` entry ("the linked aitask itself is left untouched"); shows a red
  block of running-agent casualties; `Delete` button (variant error) **disabled
  when casualties present**; double-confirm ("Are you sure?") like
  `DeleteSessionModal.on_delete`. Carry its own `DEFAULT_CSS` + a keyboard hint
  per `aidocs/framework/tui_conventions.md`.
- **`_open_delete_node_modal(self, node_id)`:** compute closure via
  `node_descendants_closure`; build agent casualties by iterating
  `get_all_agent_processes(crew_id)` + `list_agent_files(wt_path, "_status.yaml")`
  for `Running`/`Waiting` agents and matching `_recover_node_id_from_input(agent)`
  ∈ closure (agents whose node can't be recovered — compare/synthesize/module,
  multi-node — are treated as non-blocking, the verified-safe behavior); compute
  `linked_modules`; push the modal with `_on_delete_node_result` callback.
- **`_on_delete_node_result(self, node_id, confirmed)`:** on confirm, **re-check
  the agent guard** (defense-in-depth vs. a race while the modal was open); call
  `delete_node_cascade`; clear `_current_focused_node_id` if it was deleted;
  `notify` the count; `_load_existing_session()` to refresh DAG/status views.
  Synchronous — no agent dispatch (mirrors `_execute_session_op`).
- **Binding (3027):** `Binding("A", "node_action", "Node op")` →
  `Binding("A", "node_action", "Node action")`. Leave lowercase `a` (3022) alone.

### Reused existing code (do not reinvent)
- `_recover_node_id_from_input` / `_PATCHER_INPUT_META_RE` (app 4661 / 4169) —
  agent→node mapping (verified: `_status.yaml` has only `agent_name`+`status`;
  the node is recovered from `<agent>_input.md`).
- `DeleteSessionModal` (app 702) — modal + double-confirm pattern.
- `fast_track` block (app 3685) — node→module wizard seeding pattern.
- `_ancestor_subgraphs` (app 6428), `_node_module`/`get_head`/`_read_graph_state`
  (dag) — relevance computation.
- `_load_existing_session` (app 4089) — post-op refresh.

## Verification

Tests are `unittest` Python files (`python tests/test_*.py`).

The cascade-delete code-health risk is mitigated by **proper unit tests that
operate on dummy data** — each test constructs a synthetic session on a temp dir
(hand-written `br_nodes/*.yaml`, `br_proposals/*.md`, `br_plans/*_plan.md`, and a
crafted `br_graph_state.yaml`) and calls the pure `brainstorm_dag.py` helpers
directly. No live brainstorm session, agents, or Textual runtime are required, so
every graph-state edge case is exercised deterministically against fixtures.

- **Extend `tests/test_brainstorm_dag.py`** (`TestDeleteNodeCascade`), all over
  synthetic fixtures built in `setUp` (a small helper that writes the node/
  proposal/plan/graph-state files for a given shape): linear-chain cascade + HEAD
  repoint to surviving parent; delete HEAD-with-no-parent → HEAD cleared; history
  prune; **linked `module_tasks` preserved**; `plan_file` (non-default name)
  deleted; multi-parent over-delete pulls in the synthesize node; `_umbrella`
  legacy-alias consistency; `missing_root`; `node_descendants_closure` parity.
  Assert on both the returned report dict **and** the on-disk
  `br_graph_state.yaml` / file presence after the call.
- **Extend `tests/test_brainstorm_node_action_modal.py`**: disabled rows render
  their reason; `_focus_first_enabled` skips disabled new ops; `delete` row
  present/selectable (update constructor calls or rely on the `op_states` default).
- **New `tests/test_brainstorm_node_action_relevance.py`**: unit-test
  `_node_action_op_states` (umbrella → module ops disabled; linked module → sync
  enabled; no-ancestor module → merge disabled; no-plan node → patch disabled),
  bypassing `BrainstormApp.__init__` over a temp session (the pattern the modal
  test already uses).
- **New `tests/test_brainstorm_node_delete.py`**: `DeleteNodeModal` renders full
  closure + linked warning, Delete disabled when casualties present, double-confirm
  dismisses `True`; agent matching blocks a Running agent on an affected node and
  ignores an unrecoverable (multi-node) agent; `_on_delete_node_result(node, True)`
  cascades + clears focus + notifies.
- **Regression:** re-run `tests/test_brainstorm_node_action_integration.py` and
  `tests/test_brainstorm_module_ops_integration.py`.
- Lint: `shellcheck` n/a (Python); follow repo Python style.
- **Manual (live TUI):** in `ait brainstorm`, focus a module node → `A` shows all
  ops with the right ones greyed-out + reasons; pick a module op → lands in the
  correct config step; pick Delete → confirm modal lists the subtree, blocks while
  an agent runs, warns on a linked module; confirm → nodes gone, HEAD repointed,
  views refresh.

Then proceed to **Step 9 (Post-Implementation)** for cleanup/archival.

## Risk

### Code-health risk: medium
- Cascade node-delete is **destructive and irreversible** — it removes node /
  proposal / plan files and mutates `br_graph_state.yaml` (HEAD repoint, history
  prune). Subtle edge cases (multi-parent over-delete, the legacy `_umbrella`
  ⇄ `current_head` alias, HEAD repoint when the deleted root has multiple
  parents) could corrupt graph state if mishandled · severity: medium · →
  mitigation: proper `TestDeleteNodeCascade` unit tests over synthetic
  (dummy-data) sessions covering every edge case — see Verification (no separate
  follow-up task; mitigation folded into this plan)
- `brainstorm_app.py` is a large, central TUI file; the new modal + routing add
  surface to it, though the load-bearing logic is isolated in the pure
  `brainstorm_dag.py` helper and unit-tested · severity: low · → mitigation:
  keep mutation logic in `brainstorm_dag.py` (pure, unit-tested); the TUI only
  routes/renders

### Goal-achievement risk: low
- The agent guard cannot map multi-node agents (compare/synthesize/module) to a
  single node, so such an agent reading an affected node is **not** treated as a
  casualty (conservative, documented) — a deliberate scope limit, not a miss ·
  severity: low · → mitigation: none needed (documented scope limit)
