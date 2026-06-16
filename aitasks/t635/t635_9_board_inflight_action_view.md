---
priority: medium
effort: high
depends: [t635_6, t635_8]
issue_type: feature
status: Implementing
labels: [gates, aitask_board, tui]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-06-10 18:54
updated_at: 2026-06-16 12:28
---

## Context

Phase 3 of `aidocs/gates/integration-roadmap.md` (decision D7). Once tasks
linger in partial phases of completion (gates pending), the kanban board
alone makes it hard to choose WHICH task needs WHAT operation. The chosen
UX (over kanban filter+badge and phase swimlanes) is a dedicated In-Flight
view grouping tasks by NEXT REQUIRED ACTION.

## Scope

- New board view listing in-flight tasks (derived via the t635_8 parser)
  in three action groups:
  - **Needs your action** — pending human gate / failed gate needing a fix
    decision; ops: sign-off (`ait gate pass`), fail, open diff/details.
  - **Agent can continue** — next unmet checkpoint is machine-runnable or
    resumable; ops: pick-resume (spawn `/aitask-pick <n>` as today),
    run gates via `aitask-resume` (headless or in a pane).
  - **Blocked** — upstream gate/dependency failed or exhausted.
- Per-task gate summary line (icons per the framework doc marker icons).
- Keybindings via the keybinding registry; tmux spawning per
  `aidocs/framework/tui_conventions.md` (one TUI per window; agent panes as
  the board already does for pick).
- Reachable from the existing board (view toggle), and listed in the TUI
  switcher if it becomes a separate screen — design choice at planning.

## ASCII sketch (agreed during design)

    ┌─ In Flight ─────────────────────────────────┐
    │ ▼ Needs your action (2)                     │
    │   t42  pagination endpoint    ⏸ review      │
    │         [s]ign-off  [f]ail  [d]iff          │
    │ ▼ Agent can continue (1)                    │
    │   t61  docs sweep             ✅✅ ⏸ docs    │
    │         [p]ick resume  [g]ates run          │
    │ ▼ Blocked (1)                               │
    │   t49  schema migration       ⛔ upstream    │
    └─────────────────────────────────────────────┘

## Coordination (from t635_3)

The board computes dependency-blocking INDEPENDENTLY of `ait ls`
(`aitask_board.py`, the `unresolved_deps` computation: a dep is unresolved while
`status != 'Done'`). t635_3 made `aitask_ls.sh` gate-aware — a gated active
upstream whose required (`blocks_dependents`) gates pass unblocks its dependents
before archival — but deliberately left the board to this task (per the
shared-parser rule). Wire the same decision into the board's dependency
computation via `lib/gate_ledger.py dependents_status` (the shared parser from
t635_8) — do not fork. Note the interim window: after t635_4 (deferred archival)
lands but before this task, `ait board` and `ait ls` can disagree on whether a
gated, machine-passed task still blocks its dependents.

## References

- `aidocs/gates/integration-roadmap.md` (Phase 3, D7)
- `aidocs/gates/dependency-unblock-semantics.md` (t635_3 — CLI is gate-aware; board is this task)
- `aidocs/framework/tui_conventions.md`

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-06-16T09:37:51Z status=pass attempt=1 type=human
