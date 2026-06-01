---
Task: t898_refactor_brainstorm_wizard_step_machine.md
Base branch: main
plan_verified: []
---

# t898 — Refactor the brainstorm wizard step machine

## Context

`ait brainstorm`'s Actions-tab wizard tracks progress with a bare integer
`self._wizard_step` (1..`_wizard_total_steps`) in
`.aitask-scripts/brainstorm/brainstorm_app.py`. Step identity is reconstructed
at ~10 sites by comparing that int against hardcoded literals (`== 1`, `== 2`,
`== 3`, `== total`, `== total-1`) plus the `_wizard_has_sections` flag. The
optional **section-select** step is spliced in by independently recomputing
`_wizard_total_steps` (to 4/5) and hardcoding step 3. Adding one optional step
(the upcoming module **subgraph-selector**, t756_2) means editing every one of
those integer ladders and risks off-by-one "step renumbering" bugs that
silently break Back/Esc navigation. t756_2 was paused for exactly this reason
and this refactor pulled ahead of it.

**Goal:** replace the integer ladder with a declarative, ordered **step table**
+ small **pure resolver** so that (a) Back/Esc/Next/up-down dispatch and the
"Step X of Y" indicator are computed generically from the *active* step list,
and (b) adding an optional step becomes "add one table row + predicate",
touching no existing handler. Behaviour-preserving — every existing wizard path
behaves identically (one documented session-op label nuance, see below).

This is the lower-risk variant validated by design review: extract the pure
resolver and make `_wizard_step_id` the dispatch source-of-truth, but **leave
the side-effect-bearing `_actions_show_*` bodies intact** (they clear config,
seed nodes, collect sections). Only the duplicated back/escape/next ladders and
the int-literal gates are rewritten.

## The model (verified current behaviour)

Active step sequence by op family (op_select is always step 1):
- **session ops** (pause/resume/finalize/archive): op_select → confirm.
- **delete**: opens a modal, never enters the step machine (untouched).
- **explore / patch**: op_select → node_select → [section_select?] → config → confirm.
- **detail**: op_select → node_select → [section_select?] → confirm. *(no config)*
- **compare / synthesize**: op_select → config → confirm. *(no node_select)*

`section_select` is resolved **dynamically** — present only when the chosen node
has sections (a disk read), so the displayed total grows mid-flow (node_select
"of 4" → after choosing a section node, "of 5"). The refactor must reproduce
this.

## Design

### 1. Pure resolver (module-level, unit-testable, no Textual App)
Add near `_filter_labels`:

```python
class _WizardStep(NamedTuple):
    id: str
    active: Callable[[dict], bool]   # reads ONLY ctx keys
    rows: bool                       # renders OperationRow list (nav target)

_WIZARD_STEPS = [
    _WizardStep("op_select",      lambda c: True,                                   True),
    # future: _WizardStep("subgraph_select", lambda c: c["op"] in _NODE_SELECT_OPS and c.get("subgraph_count",1) >= 2, True),
    _WizardStep("node_select",    lambda c: c["op"] in _NODE_SELECT_OPS,            True),
    _WizardStep("section_select", lambda c: c["op"] in _NODE_SELECT_OPS and c.get("node_has_sections", False), False),
    _WizardStep("config",         lambda c: c["op"] in ("explore","patch","compare","synthesize"), False),
    _WizardStep("confirm",        lambda c: c["op"] not in ("delete",),             False),
]
```

Pure functions over a plain ctx dict `{"op": str, "node_has_sections": bool}`:
- `active_step_ids(ctx) -> list[str]`
- `step_position(ctx, step_id) -> (index_1based, total)`
- `next_step_id(ctx, step_id) -> str | None`
- `prev_step_id(ctx, step_id) -> str | None`

Predicates use `ctx.get(...)` so a minimal ctx never raises.

### 2. App wiring (minimal-blast-radius)
- `__init__` (~2847): add `self._wizard_step_id: str = ""`.
- `_wizard_ctx(self) -> dict`: `{"op": self._wizard_op, "node_has_sections": self._wizard_has_sections}`. (`_wizard_has_sections` is the existing cached field — reuse it; do NOT call the disk-reading `_node_has_sections` inside a predicate.)
- Each `_actions_show_*` (step1/node_select/section_select/config/confirm): set `self._wizard_step_id = "<id>"` and derive the label numbers via
  `self._wizard_step, self._wizard_total_steps = step_position(self._wizard_ctx(), "<id>")`,
  **replacing** the hardcoded `self._wizard_step = N` / `_wizard_total_steps = 4/5` lines. Keep every other line in those bodies (config-clear, node seeding, checkbox mounts, `_wizard_has_sections = True` in section_select) unchanged.
- `_set_total_steps` (~5531): reduce to resetting `self._wizard_has_sections = False` and `self._cmp_section_checks = {}` (its total computation is now derived). Keep the call sites.
- `_actions_advance_from_node_select` (~5607): keep the patch-no-plan guard and the branch logic, but **cache `self._wizard_has_sections = self._node_has_sections(node)` BEFORE transitioning** (ordering rule: next-step resolution must see the updated ctx, else section_select is skipped). Keep the detail `_wizard_config["node"] = node` seeding.

### 3. Rewrite the dispatch sites (the payoff)
- **Esc ladder** (`on_key` ~3105-3135) and **Back button** `_on_actions_back` (~6118): replace the hand-rolled `if step == total / total-1 / 3 / 2` ladders with
  `prev = prev_step_id(self._wizard_ctx(), self._wizard_step_id)` → call the matching `_actions_show_<prev>()`. (`prev` of `op_select` is None → no-op, matching `step > 1` guard.)
- **Next button** `_on_actions_next` (~6132): dispatch on `self._wizard_step_id`:
  - `node_select` → `_actions_advance_from_node_select(...)` (keep guard).
  - `section_select` → `_collect_target_sections()`, seed detail `node`, then `next_step_id` → render.
  - `config` → `_actions_collect_config()` gate, then confirm.
- **Within-step gates** (mechanical `_wizard_step == N` → `_wizard_step_id == "..."`):
  enter op-select (3137), enter node-select (3156), Tab-cycle config for compare/synthesize (3166, keep the op clause), up/down on config checkbox (3176), up/down OperationRow nav (3191 → `_wizard_step_id in ("op_select","node_select")`), up/down confirm focus (3198 → `"confirm"`), dashboard node-select focus (5186), mouse `on_operation_row_activated` (6196 op_select / 6209 node_select).
- **"A"-key modal entry** (`_on_node_action_result` ~3424-3448): no logic change — it sets `_wizard_op`, renders node_select (which now sets `_wizard_step_id`), seeds the node, and routes through `_actions_advance_from_node_select`. Verify only.
- **Leave untouched:** the "wizard active" sentinel guards that read `_wizard_step` as boolean-ish (`< 1` / `> 0` at 2913, 3103, 3545) — `_wizard_step` stays a derived int.

## Behaviour note (surface at approval)
Deriving the total from the active set changes the **session-op confirm label
only**: today pause/resume/finalize/archive show "Step 3 of 3" (an artifact of
`_set_total_steps` hardcoding 3, though there is no step 2 for them); they will
show "Step 2 of 2" — more correct, no phantom gap. Every other label is byte
-identical, including node_select "of 4" first-visit and "of 5" after visiting
sections. If strict "3 of 3" preservation is wanted instead, say so and I'll
special-case session ops in `step_position`.

## Critical file
- `.aitask-scripts/brainstorm/brainstorm_app.py` — all changes. Key anchors:
  `__init__` 2847, `on_key` 3103-3205, "A"-key handler 3424-3448,
  `_actions_show_*` 5427-6044, `_set_total_steps` 5531,
  `_actions_advance_from_node_select` 5607, `_node_has_sections` ~5909,
  `_on_actions_back`/`_on_actions_next` 6118-6157,
  `on_operation_row_activated` 6190-6232.

## Verification
- **New pure-resolver unit test** (`tests/test_brainstorm_wizard_steps.py`, no TUI):
  - active sets/totals per op family: explore/patch no-sections=4, +sections=5;
    detail=3/4 (no config); compare/synthesize=3 (no node_select); session ops=2.
  - `step_position` indices (e.g. explore+sections: node_select=(2,5),
    section_select=(3,5), config=(4,5), confirm=(5,5); compare config=(2,3)).
  - next/prev round-trips per family; `next(confirm)=None`, `prev(op_select)=None`.
  - **dynamic-total contract:** with `node_has_sections=False`,
    `next("node_select")` = config (detail: confirm); flip to True →
    `next("node_select")` = section_select. Pins the ordering rule.
- **Existing suites still pass:** `tests/test_brainstorm_wizard_filter.py`,
  `tests/test_brainstorm_wizard_sections.py`, plus the broader brainstorm tests
  (`test_brainstorm_node_action_*`, `test_brainstorm_compare_modal.py`,
  `test_brainstorm_sections.py`).
- **Manual (per `aidocs/tui_conventions.md`):** drive each op end-to-end —
  explore/patch (with and without a section-bearing node), detail, compare,
  synthesize, and a session op — exercising Enter, Next, Back, Esc, mouse click,
  the `A`-key modal entry, and up/down navigation; confirm the step indicator and
  every transition match pre-refactor behaviour.

## Step 9 (Post-Implementation)
Follow task-workflow Step 9: review, commit (`refactor: … (t898)`), consolidate
this plan with Final Implementation Notes — **document the `_WIZARD_STEPS` table
contract + resolver signatures and how to add an optional step, so t756_2 can
add `subgraph_select` as one row** — then archive via
`./.aitask-scripts/aitask_archive.sh 898`. After it lands, t756_2 (gated on this)
resumes and builds the subgraph-selector on this model.
