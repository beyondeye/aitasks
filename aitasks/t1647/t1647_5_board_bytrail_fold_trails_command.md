---
priority: medium
effort: medium
depends: [t1647_4]
issue_type: feature
status: Ready
labels: [trails, aitask_board, tui]
gates: [risk_evaluated]
anchor: 1647
created_at: 2026-09-01 18:51
updated_at: 2026-09-01 18:51
---

## Context

Fifth child of t1647 (trail-to-trail merge). Give the board's By-Trail view a
command that launches the `/aitask-merge-trails` workflow (t1647_4) with both
handles already supplied. The board NEVER merges in-process — it only builds
and spawns the launch, preserving the read-only contract pinned by
`tests/test_board_bytrail_view.py::ReadOnlyNegativeControlTests`.

**Key: `F` — "Fold Trails"** (PINNED user decision; free at App level,
matches the framework's fold vocabulary, capital like the agent-launching
`R`). Taken in By-Trail today: r R d s S v T z m M a x.

## Changes (`.aitask-scripts/board/aitask_board.py`; anchors from planning —
re-verify)

1. `Binding("F", "trail_merge", "Fold Trails")` in the By-Trail block of
   `KanbanApp.BINDINGS` (next to `M` `trail_move_wave`, ~:9011).
2. `check_action` branch (in the big By-Trail gating chain, model the
   `trail_refresh_agent` branch ~:9094ff): visible only when
   `base_filter == "bytrail"`, `active_trail_handle` is set, ≥2 trails
   discovered (otherwise the folded-candidate picker would be empty), and
   not `_trail_launch_pending`. Truthful-footer contract (t1268): never
   advertise a key that is an immediate no-op.
3. `action_trail_merge`: guard `_modal_is_active()` + re-check the
   check_action conditions (action stays reachable via command palette /
   remap / view-switch race — the guard-not-just-binding-gate rule). Then:
   - Push new `TrailMergeSelectScreen(ModalScreen)` — model
     `TrailSelectScreen` (:4471) + its item widget: lists discovered trails
     EXCLUDING the active one, each row showing owner + the §9.2 "also in"
     overlap note (reuse the overlaps dict the view already computed).
     Dismisses the chosen folded handle or None.
   - Then a confirm screen — model `MergeColumnsConfirmScreen` (:8219):
     names base (survivor, keeps its handle), folded (retired), shared-entry
     count, and states that a launched agent performs the merge after its
     own confirmation.
   - On confirm → `_launch_merge_trails([active_trail_handle,
     folded_handle])`.
4. `_launch_merge_trails(op_args)` — mirror `_launch_trail` (:12181):
   `resolve_dry_run_command(Path("."), "merge-trails", *op_args)`, prompt
   `"/aitask-merge-trails <base> <folded>"`,
   `resolve_agent_string(Path("."), "merge-trails")`, `AgentCommandScreen`
   with `operation="merge-trails"`, window name `agent-merge-trails-<suffix>`
   (sanitized), tmux/dialog launch paths, `debounce_key` for `F`
   (resolve_key("board", "trail_merge", "F")), and the
   baseline→launch→watch contract with `watch_handle` = the BASE handle
   (the merged version lands there; reload on arrival). Cancel path: no
   watch installed, existing watch preserved, no reload — exactly the
   `_launch_trail` semantics (t1268/t1279 comments there explain each
   guard; keep them true).
5. Ghost/marked-set interactions: `F` is trail-level (like `s`/`R`), not
   card-level — no per-card gating needed beyond the view-level conditions.

## Tests (`tests/test_board_bytrail_view.py`)

- Gating: hidden outside By-Trail; hidden with no active trail; hidden with
  only one discovered trail; hidden while `_trail_launch_pending`; visible
  in the happy state (extend the footer-labels test with the new key).
- Launch construction: `action_trail_merge` → picker → confirm →
  `resolve_dry_run_command` called with `("merge-trails", base, folded)`;
  prompt string carries both handles (model `TrailLaunchConstructionTests`).
- Watch: confirmed launch installs the version watch on the BASE handle;
  cancel installs none and preserves an existing watch (model
  `TrailWatchTests`).
- Picker excludes the active trail.
- Read-only negative control: the new flow spawns nothing beyond the
  pinned read verbs + the confirmed launch (extend the spawn-set
  assertions where they enumerate allowed helpers).

## Verification

- `bash tests/run_all_python_tests.sh --test-dir tests` green
  (test_board_bytrail_view.py especially).
- Manual: `ait board` → `z` → `s` (select a trail) → `F` → pick + confirm →
  AgentCommandScreen appears with the right command; Esc at each stage backs
  out cleanly. (The aggregate MV sibling re-checks end-to-end.)

Parent plan: `aiplans/p1647_merge_trails_skill_shared_helpers_board_command_docs.md`.
