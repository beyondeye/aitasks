---
Task: t1647_5_board_bytrail_fold_trails_command.md
Parent Task: aitasks/t1647_merge_trails_skill_shared_helpers_board_command_docs.md
Sibling Tasks: aitasks/t1647/t1647_1_*.md … t1647_6_*.md
Worktree: (none — profile 'fast', current branch)
Base branch: main
Output branch: main
plan_verified: []
---

# Plan: t1647_5 — Board By-Trail `F` ("Fold Trails") command + dialogs

## Context

Launch surface #1: from the board's By-Trail view, pick a trail to fold into
the active one and launch `/aitask-merge-trails <base> <folded>` (t1647_4's
two-ref shape). The board NEVER merges in-process — it builds and spawns the
launch only, preserving the read-only contract
(`ReadOnlyNegativeControlTests`). **Key `F` is a PINNED user decision.**

Read `aidocs/framework/tui_conventions.md` before editing.

## Changes — `.aitask-scripts/board/aitask_board.py` (anchors from planning;
re-verify, the file churns)

1. **Binding.** `Binding("F", "trail_merge", "Fold Trails")` in the By-Trail
   block of `KanbanApp.BINDINGS` (next to `M` `trail_move_wave`, ~:9011).
2. **`check_action` branch** (model the `trail_refresh_agent` branch in the
   By-Trail gating chain): show only when ALL hold —
   `base_filter == "bytrail"`; `active_trail_handle` set; ≥2 trails
   discovered (the picker would otherwise be empty — truthful-footer
   contract, t1268); not `_trail_launch_pending` (same double-launch
   rationale as `R`).
3. **`action_trail_merge`.** Guard `_modal_is_active()` AND re-check the
   check_action conditions in the action body (reachable via command
   palette / remap / view-switch race — guard, not just binding gate).
   Flow:
   - Push `TrailMergeSelectScreen(ModalScreen)` — model `TrailSelectScreen`
     (:4471) and its `TrailSelectItem`: rows = discovered trails EXCLUDING
     the active handle, each showing owner + the §9.2 "also in" overlap
     notes (reuse the overlaps dict the view already holds). Dismisses the
     chosen folded handle or None.
   - On a handle: push a confirm screen — model `MergeColumnsConfirmScreen`
     (:8219): names the base (survivor — keeps its handle), the folded
     trail (retired), the shared-entry count, and states that the launched
     agent performs the merge after its own confirmation (the board writes
     nothing).
   - On confirm: `_launch_merge_trails([active_trail_handle,
     folded_handle])`.
4. **`_launch_merge_trails(op_args)`** — mirror `_launch_trail` (:12181)
   faithfully, including its comment contracts:
   - `resolve_dry_run_command(Path("."), "merge-trails", *op_args)`; direct
     `CODEAGENT_SCRIPT invoke merge-trails …` fallback with the SAME
     baseline→launch→watch wrapper (the t1268 comment: the fallback must
     not opt out of the post-refresh pickup).
   - prompt `"/aitask-merge-trails <base> <folded>"`;
     `resolve_agent_string(Path("."), "merge-trails")`;
     `AgentCommandScreen(..., operation="merge-trails",
     default_window_name="agent-merge-trails-<sanitized suffix>",
     skill_name="merge-trails", debounce_key=resolve_key("board",
     "trail_merge", "F") or "F")`.
   - `watch_handle` = the BASE handle (the merged version lands there;
     By-Trail reloads on arrival). Watch installed only on a CONFIRMED
     launch; cancel installs nothing, preserves an existing watch, skips
     the reload — exactly `_launch_trail`'s cancel semantics.
   - Factor shared body with `_launch_trail` where it stays readable
     (e.g. a common `_launch_trail_operation(operation, op_args, …)`), but
     do not force it — two small mirrors beat one tangled generic.
5. `F` is trail-level (like `s`/`R`), not card-level — no per-card ghost
   gating beyond the view-level conditions.

## Tests — `tests/test_board_bytrail_view.py`

- **Gating:** hidden outside By-Trail; hidden with no active trail; hidden
  with a single discovered trail; hidden while `_trail_launch_pending`;
  visible in the happy state. Extend the footer-labels test
  (`test_bytrail_footer_labels`) with `F Fold Trails`.
- **Launch construction** (model `TrailLaunchConstructionTests`):
  picker → confirm → `resolve_dry_run_command` receives
  `("merge-trails", base, folded)`; the prompt string carries both handles;
  window name shape.
- **Picker content:** excludes the active trail; shows overlap notes.
- **Watch** (model `TrailWatchTests`): confirmed launch installs the
  version watch on the BASE handle; cancel installs none and preserves an
  existing watch; tmux-launch failure installs none.
- **Read-only negative control:** extend the allowed-spawn enumerations so
  the new flow's only subprocess beyond the pinned read verbs is the
  confirmed launch; the stored artifacts stay byte-identical.

## Verification

- `bash tests/run_all_python_tests.sh --test-dir tests` green
  (test_board_bytrail_view.py fully).
- Manual: `ait board` → `z` → `s` → `F` → pick → confirm →
  AgentCommandScreen shows the right command; Esc backs out at every stage;
  `F` absent from the footer outside By-Trail and with <2 trails. (The MV
  sibling re-checks end-to-end with a real launch.)
