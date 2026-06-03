---
Task: t756_5_phase_d1_status_views.md
Parent Task: aitasks/t756_brainstorm_modules.md
Sibling Tasks: aitasks/t756/t756_1_phase_a_data_model.md, aitasks/t756/t756_2_phase_b1_module_aware_wizard_infra.md, aitasks/t756/t756_3_phase_b2_decompose_merge_ops.md, aitasks/t756/t756_4_phase_c_sync_op.md, aitasks/t756/t756_6_phase_d2_fast_track_preset.md
Archived Sibling Plans: aiplans/archived/p756/p756_1_*.md … p756_4_*.md
Worktree: (none — current branch)
Branch: main
Base branch: main
plan_verified:
  - claudecode/opus4_8 @ 2026-06-03 09:39
---

# t756_5 — Phase D1: status views (badges + dashboard + deferred marker)

**Primary reference:** `aidocs/brainstorming/module_decomposition_design.md`
(§4.7 fluid status as a derived view, §7 Phase D). **Binding conventions:**
`aiplans/p756_brainstorm_modules.md`. **TUI rules:** `aidocs/tui_conventions.md`.
**Depends on:** t756_4 (sync state, merge 'merged' status, full data model) — **landed & archived.**

> **VERIFIED 2026-06-03 (verify path).** All plan anchors re-checked against the
> as-landed code after t756_1–4 shipped. Approach holds. Concrete corrections
> below (paths/line-drift, deferred-marker persistence shape, status resolution).

## Goal
The status-visualization half of the original Phase D. UC-2 (fluid status) is a
**derived render, not a new op** — all inputs already exist after A/B/C. Surface a
per-module status badge, a subgraph-tree dashboard, and the deferred-module marker.
(The fast-track wizard preset is split to D2, t756_6.)

## Verification findings (what changed since the plan was written)

The brainstorm modules live under **`.aitask-scripts/brainstorm/`** (the plan's bare
filenames resolve there). All referenced helpers exist; line numbers drifted:

| Anchor | Plan said | As-landed (`.aitask-scripts/brainstorm/`) |
|--------|-----------|--------------------------------------------|
| `_module_tasks_map(wt)` | `brainstorm_session.py:~1223` | `brainstorm_session.py:1231` |
| `FuzzyCheckList.set_grouped_items` | `brainstorm_app.py:~1654` | `brainstorm_app.py:1834–1860` |
| `extract_dimensions` / `group_dimensions_by_prefix` | `brainstorm_schemas.py:~145,~150` | `brainstorm_schemas.py:188–190 / 193–213` |
| `get_active_dimensions` | `brainstorm_dag.py:~116` | `brainstorm_dag.py:129–132` |
| `OP_BADGE_STYLES` | `brainstorm_dag_display.py:~60` | `brainstorm_dag_display.py:60–71` |

Four substantive corrections feed the implementation:

1. **No `linked_task` field exists** (the §4.7 table uses it as a *concept*). The
   linkage is `module_tasks[module] = task_id` in `br_graph_state.yaml`
   (`GRAPH_STATE_MODULE_MAPS`, `brainstorm_schemas.py:48`). Read it via the existing
   getter `_module_tasks_map(wt)` (`brainstorm_session.py:1231`). "no `linked_task`"
   in the status table ⇒ "no `module_tasks` entry for this subgraph".
2. **Status resolution from a task_id needs a live-vs-archived task-file lookup.**
   `module_tasks[m]` stores a bare id (e.g. `756_5`), not a path. Resolve it to a
   task file and read frontmatter `status`:
   - live child `aitasks/t<parent>/t<id>_*.md` / live parent `aitasks/t<id>_*.md`
     → `status` ∈ {Ready→`in_design`, Implementing→`in_implementation`}; absent
     entry → `in_design`/`unstarted` per node count.
   - archived `aitasks/archived/t<parent>/…` → `implemented` (Done).
   Reuse the `_resolve_linked_plan_path(task_id)` resolution pattern
   (`brainstorm_crew.py:942`, live→archived fallback) and `parse_frontmatter`
   (`board/task_yaml.py:69`). The task-file (not plan-file) resolver is the one
   genuinely-new helper this task adds.
3. **`merged` detection** = walk `parents` of destination-subgraph nodes for the
   source HEAD. Helpers exist: `get_head(session_path, module)` (`brainstorm_dag.py:135`),
   `get_parents(session_path, node_id)` (`:209`), `list_nodes`/`list_subgraphs`
   (`:103,:249`), per-module `history[module]` counts, and `_node_module(node)`
   (`:225`) — which **exists but is currently unused in the display layer**.
4. **Deferred marker → flat `module_deferred` map, not nested `status.deferred`.**
   No deferred marker exists today. Follow the proven `last_synced_at` pattern:
   add `"module_deferred"` to `GRAPH_STATE_MODULE_MAPS` (`brainstorm_schemas.py:48`),
   seed `{}` in `init_session` (`brainstorm_session.py:126–134`), and add a
   getter/setter pair mirroring `_module_tasks_map` / `_write_last_synced`
   (`brainstorm_session.py:1238–1249`). This is cleaner and read/write-symmetric
   with the other module maps. The §4.7 `deferred` status is orthogonal — it
   overlays on top of the computed base status.

`module_sync` already claimed Dracula `#D6ACFF` (t756_4). Status, however, is **not
an op** — it does **not** go in `OP_BADGE_STYLES`; it is a separate status indicator
(distinct glyph/color set, see step 2). No op-badge collision.

## Scope (`.aitask-scripts/brainstorm/`)
- **Per-module status badge** per §4.7 (a render, not an op):
  | Status | Computed from |
  |--------|---------------|
  | `unstarted` | only the subgraph root exists |
  | `in_design` | nodes beyond root; no `module_tasks` entry or its task is `Ready` |
  | `in_implementation` | linked task is `Implementing` |
  | `implemented` | linked task is `Done` (archived) |
  | `merged` | source HEAD appears in `parents` of some destination-subgraph node |
  | `deferred` | explicit user marker (`module_deferred[m]`); orthogonal |
- **Dashboard** showing the subgraph tree with per-module sync/merge state.
- **Deferred-module marker** — TUI binding to set `module_deferred[m]=true` (persisted).

## Reuse (do NOT reinvent)
- `_module_tasks_map` / `_write_last_synced` pattern → new `module_deferred` getter/setter.
- `get_head` / `get_parents` / `list_subgraphs` / `history[module]` / `_node_module`
  → status computation inputs (`brainstorm_dag.py`).
- `FuzzyCheckList.set_grouped_items(groups)` (`brainstorm_app.py:1834`) → dashboard
  grouped/filterable list. `groups` = `list[(subheader, [(label, checked), …])]`.
- The t873 section-count badge loop (`brainstorm_app.py:5399–5429`, `DimensionRow`
  render `:1970`) → model for per-module status-badge computation + attachment.
- Binding pattern via `register_app_bindings(...)` + `action_*` (`brainstorm_app.py:2987`).

## Implementation steps
1. **Status computation** — pure function `compute_module_status(session_path, module)`
   (new, in `brainstorm_dag.py` or a small `brainstorm_status.py`): node-count +
   `module_tasks` task-status + `parents`-walk → one of the 6 base states; overlay
   `module_deferred[m]`. Add the live-vs-archived task-status resolver it needs.
2. **`module_deferred` map** — schema entry + `init_session` seed + getter/setter
   pair (mirror `last_synced_at`).
3. **Badge render** — per-module status badge in the dashboard/tree (separate from
   `OP_BADGE_STYLES`; model attachment on the `DimensionRow` section-count loop).
4. **Subgraph-tree dashboard** — reuse `FuzzyCheckList.set_grouped_items`; wire
   `_node_module()` into the graph build so nodes group by subgraph; show per-module
   sync (`last_synced_at`) / merge state. Keep selected rows visible under filter
   (tui_conventions §"filters keep selected rows visible").
5. **Deferred toggle binding** — `show=True` footer binding + `action_toggle_deferred`
   that flips `module_deferred[m]` and refreshes. **No git commit/push from the
   action** (tui_conventions: no runtime auto-commit of project state).

## Verification
- Per-module status badges reflect mixed states correctly
  (`unstarted`/`in_design`/`in_implementation`/`implemented`/`merged`/`deferred`),
  incl. a module that is both `deferred` and a base state (orthogonality).
- `deferred` toggle persists across a TUI reload (`module_deferred` round-trips).
- Dashboard renders the subgraph tree with per-module sync/merge state.
- `merged` detected via the cross-subgraph `parents` walk; `implemented` resolved
  from the archived task file. Unit-test the pure `compute_module_status` over
  seeded graph state (seed pattern: `tests/test_brainstorm_apply_module_ops.py:38`).
- Existing brainstorm tests still pass (`bash tests/test_brainstorm_*.sh`,
  `tests/test_brainstorm_dag.py`, module-ops tests); follow `aidocs/tui_conventions.md`.
- (Human-observable TUI behavior covered by the aggregate manual-verification
  sibling t756_7.)

## Risk

### Code-health risk: medium
- Additive but spans 5 central brainstorm files (`brainstorm_schemas.py`,
  `brainstorm_session.py`, `brainstorm_dag.py`, `brainstorm_app.py`,
  `brainstorm_dag_display.py`); wiring the previously-unused `_node_module()` into
  the core graph-build path for the dashboard is the one change that touches an
  existing render path rather than purely adding alongside it · severity: medium · → mitigation: t922
- Net-new subgraph-tree dashboard view (reuses `FuzzyCheckList`, but the
  module-grouped tree is new UI with no prior analog in the display layer) ·
  severity: low · → mitigation: TBD

### Goal-achievement risk: medium
- The `merged` (cross-subgraph `parents` walk) and `implemented` (live-vs-archived
  task-file resolution) computations are the two states most likely to be subtly
  wrong, and both are new cross-reference logic; a mis-scoped walk or a missed
  archived-path case yields a silently-wrong badge · severity: medium · → mitigation: t922
- Live TUI wizard/binding/reload cycle is not exercised this session (static +
  unit checks only) · severity: medium · → mitigation: t756_7

### Planned mitigations
- timing: after | name: module_status_compute_contract_tests | created: t922 | type: test | priority: medium | effort: medium | addresses: goal-achievement (merged/implemented status correctness) + code-health (_node_module graph-build wiring regression guard) | desc: Contract/unit coverage for compute_module_status across all 6 states over seeded graph state — cross-subgraph merged parents-walk, live-vs-archived implemented resolution, deferred overlay + module_deferred round-trip. Parallels t756_4's t913. (In-task suite test_brainstorm_module_status.py already covers the core; t922 hardens edge/combinatoric cases + a render-layer regression guard.)

## Final Implementation Notes

- **Actual work done:** Implemented the §4.7 status views end-to-end.
  - New `brainstorm_status.py` (pure, read-only): `compute_module_status` (base
    state, `merged` as terminal override), `is_module_merged` (cross-subgraph
    `parents`-walk for the source HEAD), `_resolve_task_state` (live-vs-archived
    task-file frontmatter resolution, modelled on `_resolve_linked_plan_path`),
    `module_status_rows` (per-subgraph render data: status + deferred overlay +
    sync/link/count).
  - Data model: added `module_deferred` to `GRAPH_STATE_MODULE_MAPS`
    (`brainstorm_schemas.py`), seeded `{}` in `init_session`, and added
    `_module_deferred_map` / `_write_module_deferred` mirroring `last_synced_at`
    (`brainstorm_session.py`).
  - Render: `MODULE_STATUS_STYLES` badge palette in `brainstorm_dag_display.py`,
    kept **separate** from `OP_BADGE_STYLES` (status is a render, not an op).
  - TUI (`brainstorm_app.py`): per-module status section in the Dashboard detail
    pane (`_update_module_status`, refreshed on load + HEAD change) + the `f` →
    `action_toggle_deferred` binding (tab-scoped via `check_action`, read-only /
    `_umbrella` guarded, no git auto-commit per tui_conventions).
  - Tests: `tests/test_brainstorm_module_status.py` (10 tests).
- **Deviations from plan:** Surfaced the subgraph tree as a **read-only status
  section in the existing Dashboard detail pane** rather than (a) rewiring the DAG
  `_build_graph` layering or (b) using `FuzzyCheckList.set_grouped_items` (a
  checkbox/multi-select list — wrong semantics for a read-only status render).
  `_node_module` is consumed by `module_status_rows` for per-subgraph grouping but
  the load-bearing DAG graph-build path is **left untouched** — this *retires* the
  medium code-health risk the plan flagged (no change to an existing render path).
  The deferred toggle targets the **focused node's** subgraph (reusing existing
  `_current_focused_node_id` focus infra) instead of a new focusable module-row
  widget — no new navigation surface. Both deviations reduce blast radius while
  delivering all three §4.7 deliverables (badge, dashboard, deferred marker).
- **Issues encountered:** None. The `board.task_yaml.parse_frontmatter` helper is
  not cleanly importable (`board/` is not a package — no `__init__.py`), so
  `_read_frontmatter_status` uses a small self-contained regex + `yaml.safe_load`
  (only the `status` string is read, so the `85_2`→int coercion quirk is moot).
- **Key decisions:** `merged` is the terminal state (overrides implemented/in_design)
  since a merged subgraph's design was absorbed upstream. `deferred` is an
  **orthogonal overlay** (separate boolean), not a base state — so a module can be
  both deferred and e.g. in_design (verified). Status badge colors are a distinct
  palette from op badges. Map accessors co-located with the other two module maps
  in `brainstorm_session.py` per the plan.
- **Upstream defects identified:** None.
- **Notes for sibling tasks (D2 / t756_6):**
  - `module_deferred` is the third `GRAPH_STATE_MODULE_MAPS` entry; read it via
    `_module_deferred_map(wt)`, write via `_write_module_deferred(wt, module, bool)`.
  - `brainstorm_status.compute_module_status` / `module_status_rows` are the single
    source of truth for fluid status — reuse, do not recompute. `MODULE_STATUS_STYLES`
    (in `brainstorm_dag_display.py`) is the badge palette.
  - The fast-track preset (D2) sets `module_tasks[module]` at decompose time; once
    that linkage exists, the status badge auto-advances Ready→in_design,
    Implementing→in_implementation, Done/archived→implemented with no extra wiring.
  - `_resolve_task_state(task_id)` resolves a bare task id to `(status, is_archived)`
    over `aitasks/` (live→archived) — reuse it for any task-status lookup from the TUI.

## Step 9 (Post-Implementation)
Follow task-workflow Step 9: review, commit (`feature: … (t756_5)`), consolidate this
plan with Final Implementation Notes (status-resolution helper shape + notes for
D2/t756_6), archive via `./.aitask-scripts/aitask_archive.sh 756_5`.
