---
Task: t756_6_phase_d2_fast_track_preset.md
Parent Task: aitasks/t756_brainstorm_modules.md
Sibling Tasks: aitasks/t756/t756_1_phase_a_data_model.md, aitasks/t756/t756_2_phase_b1_module_aware_wizard_infra.md, aitasks/t756/t756_3_phase_b2_decompose_merge_ops.md, aitasks/t756/t756_4_phase_c_sync_op.md, aitasks/t756/t756_5_phase_d1_status_views.md
Archived Sibling Plans: aiplans/archived/p756/p756_1_*.md … p756_5_*.md
Worktree: (none — current branch)
Branch: main
Base branch: main
plan_verified:
  - claudecode/opus4_8 @ 2026-06-03 11:12
---

# t756_6 — Phase D2: "Fast-track this module" wizard preset

**Primary reference:** `aidocs/brainstorming/module_decomposition_design.md`
(§4.8 UC-3 = decompose `--modules=one` + `link_to_task`; §7 Phase D). **Binding
conventions:** `aiplans/p756_brainstorm_modules.md`. **TUI rules:**
`aidocs/tui_conventions.md`. **Depends on:** t756_5 (landed & archived).

> **VERIFIED 2026-06-03 (verify path).** Plan anchors re-checked against the
> as-landed code after t756_1–5 shipped. The functional `module_decompose
> --link-to-task` path (B2/t756_3) and the D1 dashboard surfaces (t756_5) are
> present and unchanged. Design refined to a concrete, minimal-blast-radius
> approach; corrections below.

## Goal
The **ergonomics** half of the original Phase D: a polished one-pass "Fast-track
this module" wizard preset over the functional `module_decompose --link-to-task`
path that landed in B2 (t756_3). UC-3 is just `module_decompose` parameterised
(one module + `link_to_task`) — this is a **presentation/UX layer, not a new
op**. Both paths route through the same `register_module_decomposer()` call.

## Context
Today, fast-tracking one module into a linked aitask requires driving the full
multi-module decompose wizard: pick op (Module Decompose) → pick subgraph → type
a module list → tick "Create linked child tasks" → confirm. UC-3 is the common
single-module case; D2 collapses that into a one-pass preset reachable directly
from a focused node, with `link_to_task` pre-armed.

## Verification findings (anchors re-checked against as-landed code)

All in `.aitask-scripts/brainstorm/`:

| Anchor | Status |
|--------|--------|
| `register_module_decomposer(..., link_to_task=False, ...)` | `brainstorm_crew.py:849` ✓ — the `link_to_task` functional path (creates child aitask + writes `module_tasks[M]`) is intact. |
| `_execute_design_op` → `module_decompose` branch | `brainstorm_app.py:7044` ✓ — calls `register_module_decomposer(..., link_to_task=cfg["link_to_task"], ...)`. This is the single execution path the preset must reuse. |
| `_config_module_decompose` | `brainstorm_app.py:6364` ✓ — mounts modules `TextArea`, `chk_from_sections`, `chk_link_to_task`, plan `TextArea`. |
| Config collection / confirm / execute for `module_decompose` | `brainstorm_app.py:6577 / 6746 / 7044` ✓. |
| `NodeActionSelectModal` (`A`-key single-node op picker) + `_OPS=["explore","detail","patch"]` | `brainstorm_app.py:2033` ✓. |
| `_on_node_action_result` (seeds wizard from a focused node) | `brainstorm_app.py:3654` ✓. |
| `_set_total_steps` (per-op flag reset funnel; sets `_wizard_subgraph=UMBRELLA_SUBGRAPH`) | `brainstorm_app.py:5949` ✓. |
| `_node_module()` / `UMBRELLA_SUBGRAPH` available in app | ✓ (used by `action_toggle_deferred`, `brainstorm_app.py:3641`). |

**Correction to the task's reuse hint:** the task text suggests reusing
`FuzzyCheckList.set_grouped_items` (and cites `~1654`; actual `brainstorm_app.py:1840`).
This design does **not** need it — the preset reuses the existing
`_config_module_decompose` form (a plain module-name `TextArea`), not a grouped
selection list. No grouped-list UI is introduced. (Hint noted as N/A.)

## Approach — preset = a fourth entry in the node-action picker

The `A`-key `NodeActionSelectModal` already does exactly the "operate on the
focused thing → seed the wizard" dance (via `_on_node_action_result`). The
preset rides that surface instead of inventing a new binding or a fake op:

1. **`NodeActionSelectModal`** (`brainstorm_app.py:2033`): add a fourth picker
   entry `"fast_track"` after explore/detail/patch, with an explicit
   label/description ("Fast-track this module" / "Extract one module into a
   linked aitask in a single pass"). Labels come from a small local map in the
   modal (the existing `_OP_LABELS` has no `fast_track` key, by design — it is
   **not** a real op). Always enabled (decompose is valid from any subgraph
   HEAD, incl. `_umbrella`); the modal is only opened when the session is
   editable (`action_node_action` already guards `read_only` + status).

2. **`_on_node_action_result`** (`brainstorm_app.py:3654`): add an early branch
   for `op_key == "fast_track"`:
   - `self._wizard_op = "module_decompose"` then `self._set_total_steps()`.
   - `self._wizard_fast_track = True` (set **after** `_set_total_steps`, which
     resets it — see step 4).
   - `self._wizard_subgraph = _node_module(self.session_path, node_id)` (the
     focused node's subgraph becomes the decompose source — `module_decompose`
     reads `source_node` from `get_head(module=self._wizard_subgraph)` at
     config-collection time, `brainstorm_app.py:6579`).
   - `self._wizard_config = {}` then `self._actions_show_config()` (render the
     `module_decompose` config step directly — it has no `node_select` step, and
     the subgraph is already known, so `subgraph_select` is skipped too).
   - `self.call_after_refresh(self._enter_actions_tab)` (reuse the existing
     deferred tab-entry, identical to the node-select path).
   The existing node-select branch is unchanged.

3. **`_config_module_decompose`** (`brainstorm_app.py:6364`): when
   `getattr(self, "_wizard_fast_track", False)`:
   - pre-check the linked-task checkbox: build it, set `.value = True` before
     mounting;
   - add a one-line `[dim]` hint (e.g. "Fast-track: name one module → linked
     task created in one pass");
   - everything else (modules `TextArea`, from_sections, plan, Next button)
     stays. The user types the single module name and confirms. Confirm
     (`6746`) + execute (`7044`) are **untouched** — the preset reaches the
     identical `register_module_decomposer(..., link_to_task=True, ...)` call.

4. **Flag lifecycle (the one cross-cutting edit — guard against leak).**
   `_wizard_fast_track` is transient wizard state. It MUST reset whenever a new
   operation is chosen so the preset's pre-check does not bleed into a later
   normal `module_decompose`. Initialise `self._wizard_fast_track = False` in
   `BrainstormApp.__init__` (alongside the other `_wizard_*` defaults) and reset
   it to `False` in `_set_total_steps()` (`brainstorm_app.py:5949`) — the single
   funnel every op-select call-site already routes through (op-select Enter
   `3331`, session-op `3331`, the fast-track branch itself, node-action `3671`).
   Resetting there, then re-arming only on the fast-track branch, makes the leak
   structurally impossible.

### Why this shape (cleanliness / blast-radius)
- **No new op.** `op` stays `"module_decompose"` end to end — no new op-key,
  agent-type, template, help text, `_OP_LABELS`, `GROUP_OPERATIONS`, or
  `_execute_design_op` branch. The task's binding constraint ("both route through
  the same `register_module_decomposer()`; §4.8 — no new op") is met by
  construction.
- **No new persisted state / data model.** Pure transient UI flag; nothing
  written to `br_graph_state.yaml`. `module_tasks[M]` is still written by the
  existing `link_to_task` apply path.
- **Reuses the proven seeding infra** (`_on_node_action_result` +
  `_enter_actions_tab`) rather than a parallel launch path.
- **Single funnel reset** neutralises the "someone edits this later, unaware"
  failure mode: any new op-select clears the flag.

### Alternatives considered and rejected
- **A "fast_track" pseudo-op in `_DESIGN_OPS` (Step 1 op list).** Rejected: it
  would pollute the op vocabulary (op-key, `_WIZARD_OP_TO_AGENT_TYPE`,
  `_OP_LABELS`, help, execute switch) with a fake op that is really
  `module_decompose` — precisely the "forked op logic" the task forbids.
- **A dedicated Dashboard keybinding (like `f` for defer).** Rejected: adds a
  top-level binding + Footer entry for a rarely-used preset; the `A` picker
  already aggregates per-node operations and is the natural home (less surface).

## Files to modify
- `.aitask-scripts/brainstorm/brainstorm_app.py` — the four edits above
  (`NodeActionSelectModal`, `_on_node_action_result`, `_config_module_decompose`,
  `_set_total_steps` + `__init__`).
- `tests/test_brainstorm_node_action_modal.py` — extend (see Verification).

## Implementation steps
1. `NodeActionSelectModal`: add `"fast_track"` to `_OPS`; provide its label/desc
   locally; keep it enabled.
2. `_on_node_action_result`: add the `fast_track` branch (seed
   `module_decompose` + `_wizard_fast_track=True` + subgraph-from-node + render
   config + deferred tab entry).
3. `_set_total_steps`: reset `_wizard_fast_track=False`; `__init__`: initialise
   it `False`.
4. `_config_module_decompose`: pre-check `chk_link_to_task` + add hint when
   `_wizard_fast_track`.
5. Tests + run the brainstorm suite.

## Verification
- The preset routes through the **same** `register_module_decomposer()` /
  `_execute_design_op` `module_decompose` branch as the multi-module path — no
  forked op logic (assert `op` stays `"module_decompose"` through seed→execute).
- Choosing "Fast-track this module" on a focused node seeds the wizard so that,
  in one config pass, a single-module `module_decompose` with `link_to_task=True`
  runs → creates a per-module subgraph root **and** a linked aitask
  (`module_tasks[M]` written by the existing B2 apply path).
- `_wizard_fast_track` does not leak: after a fast-track seed, selecting any
  other op (which calls `_set_total_steps`) clears the flag, so a subsequent
  normal `module_decompose` does **not** pre-check link-to-task.
- **Tests** (mirror `tests/test_brainstorm_node_action_modal.py`, the
  established Pilot + `__init__`-bypass pattern):
  - `NodeActionSelectModal` now exposes 4 rows incl. `fast_track`, enabled,
    returns `"fast_track"` on select.
  - `_on_node_action_result("...", "fast_track")` sets `_wizard_op ==
    "module_decompose"`, `_wizard_fast_track == True`, `_wizard_subgraph` ==
    the node's module, and renders config (not node-select).
  - `_set_total_steps()` resets `_wizard_fast_track` to `False`.
  - Existing brainstorm tests still pass: `bash tests/test_brainstorm_*.sh`,
    `python tests/test_brainstorm_node_action_modal.py`,
    `tests/test_brainstorm_module_ops_integration.py`,
    `tests/test_brainstorm_wizard_steps.py`.
- (Live in-TUI flow — focus node → `A` → Fast-track → confirm → agent launch →
  linked task on disk — is human-observable and covered by the aggregate
  manual-verification sibling **t756_7**, consistent with §"full BrainstormApp
  boot is not an established test pattern".)
- Follow `aidocs/tui_conventions.md`.

## Risk

### Code-health risk: low
- Additive and localized to four small edits in one file; the only cross-cutting
  change is the transient `_wizard_fast_track` flag, whose leak risk is fully
  neutralised by resetting it in the single `_set_total_steps` op-select funnel
  · severity: low · → mitigation: None needed (reset-at-funnel + flag-reset
  unit test).
- Reuses the existing `_on_node_action_result` seeding path rather than adding a
  parallel launch path; touches that established render path but only via an
  early `op_key == "fast_track"` branch that leaves the node-select path intact
  · severity: low · → mitigation: covered by the modal/callback unit tests.

### Goal-achievement risk: medium
- The full one-pass live TUI flow (focus → `A` → Fast-track → pre-checked config
  → confirm → agent launch → linked aitask + `module_tasks[M]` on disk) is not
  exercised by unit tests (no full-`BrainstormApp`-boot pattern in this repo);
  static + seeding unit checks only · severity: medium · → mitigation: t756_7
  (existing aggregate manual-verification sibling).

### Planned mitigations
(none new — the live-flow goal-achievement risk is already owned by the
existing aggregate manual-verification sibling **t756_7**, which runs after this
task per the parent's `children_to_implement: [t756_6, t756_7]`.)

## Final Implementation Notes

- **Actual work done:** Implemented the "Fast-track this module" preset (UC-3)
  exactly as designed — five edits, all in
  `.aitask-scripts/brainstorm/brainstorm_app.py`:
  1. `BrainstormApp.__init__` — added the transient `_wizard_fast_track = False`
     default alongside the other `_wizard_*` fields.
  2. `_set_total_steps()` — resets `_wizard_fast_track = False` (the single
     op-select funnel), so the preset's arm can never leak into a later op.
  3. `NodeActionSelectModal` — added `"fast_track"` to `_OPS` and a local
     `_LOCAL_LABELS` map ("Fast-track this module" / "Extract one module into a
     linked aitask in a single pass"); `compose()` now reads `_LOCAL_LABELS`
     first, then falls back to `_OP_LABELS`. Always enabled (not gated on
     `has_plan`).
  4. `_on_node_action_result()` — new early `op_key == "fast_track"` branch:
     sets `_wizard_op = "module_decompose"`, calls `_set_total_steps()`, re-arms
     `_wizard_fast_track = True`, sets `_wizard_subgraph` from the focused node's
     module (`_node_module`), clears `_wizard_config`, renders config directly,
     and defers the Actions-tab entry. The node-select branch is unchanged.
  5. `_config_module_decompose()` — when `_wizard_fast_track`, pre-arms the
     "Create linked child tasks" checkbox (`link_chk.value = True`) and shows a
     one-line dim hint. The confirm (`6746`) and execute (`7044`) paths are
     untouched — the preset reaches the identical
     `register_module_decomposer(..., link_to_task=True, ...)` call.
- **Deviations from plan:** None. The design held verbatim. The checkbox
  pre-arm was implemented by building the `Checkbox` and setting `.value`
  before `mount()` (the cleanest way to pre-check a Textual `Checkbox`).
- **Issues encountered:** None.
- **Key decisions:** `fast_track` is intentionally **not** a real op — `op`
  stays `"module_decompose"` end to end (no new op-key / agent-type / template /
  `_OP_LABELS` / `GROUP_OPERATIONS` / execute branch). Its label therefore lives
  in the modal-local `_LOCAL_LABELS`, not `_OP_LABELS`. Leak-safety is enforced
  structurally: the flag is reset in the one `_set_total_steps` funnel every
  op-select routes through, and re-armed only on the fast-track branch.
- **Upstream defects identified:** None.
- **Notes for sibling tasks (t756_7, manual verification):**
  - The live flow to verify: on the Dashboard/Graph tab, focus a node, press
    `A`, choose "Fast-track this module" → the Actions wizard opens on the
    module_decompose **config** step with "Create linked child tasks" already
    ticked and a fast-track hint shown. Type one module name → Next → Confirm →
    a per-module subgraph root is created and (link-to-task) a child aitask is
    created with `module_tasks[<module>]` written.
  - Regression to eyeball: after using fast-track, open the normal Module
    Decompose op from Step 1 — its link-to-task checkbox must be **unchecked**
    (flag did not leak).
  - Unit coverage added in `tests/test_brainstorm_node_action_modal.py`
    (4-row modal incl. enabled `fast_track`; `_on_node_action_result` seeding;
    `_set_total_steps` flag reset). Full BrainstormApp boot remains
    manual-verification territory.
- **Tests:** `tests/test_brainstorm_node_action_modal.py` (20 pass);
  full brainstorm python + shell suites green.

## Step 9 (Post-Implementation)
Follow task-workflow Step 9: review, commit (`feature: … (t756_6)`), consolidate
this plan with Final Implementation Notes, archive via
`./.aitask-scripts/aitask_archive.sh 756_6`. This is the last *implementation*
child; the manual-verification sibling (t756_7) runs after it.
