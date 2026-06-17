---
priority: medium
effort: high
depends: []
issue_type: refactor
status: Ready
labels: [brainstorming, tui, ait_brainstorm]
children_to_implement: [t983_10, t983_11]
created_at: 2026-06-14 10:52
updated_at: 2026-06-17 12:11
boardidx: 10
---

Redesign the information architecture of the `ait brainstorm` TUI
(`.aitask-scripts/brainstorm/brainstorm_app.py`, ~7,900 lines) to fix a
structural UX smell and consolidate around **contextual node operations**.

This is a **refactoring umbrella task** — it must be split into child tasks at
planning time (run via `/aitask-pick`, which builds the detailed plan against
the as-landed codebase). Decomposition guidance is given below.

## Problem (current design)

The TUI is a single `TabbedContent` with **5 peer tabs** — `(D)ashboard`,
`(G)raph`, `(C)ompare`, `(A)ctions`, `(S)tatus` — that flatten **four different
*kinds* of things** into one "tabs" metaphor:

- **Views** of the same node DAG → Dashboard (list) and Graph (DAG) are two
  shapes of identical data on separate tabs, each carrying its own right-hand
  detail pane.
- **A transient analysis** → Compare is an operation over a selected node set,
  but it lives as a tab that is blank until you press `r`.
- **A flow** → Actions is a multi-step wizard (a stepper), not a destination.
- **A monitor** → Status is a passive runtime readout whose name is opaque.

Concrete consequences:
1. Node detail is rendered in **3 places** (Dashboard pane, Graph pane,
   `NodeDetailModal`) — duplicate, drift-prone.
2. Switching the *shape* of the same data requires a *tab* switch.
3. Compare-as-tab is heavyweight for what is a contextual operation.
4. Two ways to run ops (the Actions wizard tab **and** the `A`
   `NodeActionSelectModal`) hurts discoverability.
5. "Status" does not convey that it is a runtime monitor.
6. `A` (node actions) has no visible affordance.

Key insight (from the design discussion): **every op in the current Actions tab
is a node operation** — some single-node (explore, module_decompose/merge/sync,
fast_track, delete), some multi-node (compare, synthesize). They belong *on the
node selection*, not in a standalone tab.

## Target design (converged — "Direction A", refined)

Collapse **5 tabs → 3** and move node operations into contextual dialogs.
A command-palette approach was explicitly **rejected**: it hides ops behind
typing and discards the op list's built-in explanations
(`_OPERATION_HELP` + per-op descriptions), which are how a less-experienced
user discovers and understands which op to run. That discoverability must be
preserved — the op-list-with-descriptions becomes a **contextual dialog**, not
a palette.

```
Header: title · t<N> — name · [runner ●] [▶ N running]      ← always-on status strip
Tabs:  BROWSE (b) · SESSION (s) · RUNNING (r)                 ← was D/G/C/A/S

BROWSE   graph ⇄ recent-list toggle (v)  |  ONE shared NodeDetailPanel
         graph is the default view; the toggle persists per session
         space = mark node(s)            ← single OR multi selection
         Enter → Node Hub (Detail)
         A     → Operations dialog (contextual to the current selection)
SESSION  lifecycle ops list w/ descriptions:
         pause · resume · finalize · archive · delete   (+ confirm modals)
RUNNING  renamed Status monitor (full detail)

Contextual dialogs / overlays:
  Node Hub (Enter)        Detail · Operations
  Operations dialog (A)   THE op list w/ descriptions — explore · compare ·
                          synthesize · module_decompose/merge/sync · fast_track ·
                          delete. Each row enabled/disabled by the current
                          selection (reuse NodeActionSelectModal's op_states +
                          reason pattern): single-node ops greyed when N marked,
                          multi-node ops (compare/synthesize) greyed when only 1.
                          Choosing an op launches the existing wizard, SEEDED
                          with the selection (its "pick node(s)" step is dropped,
                          replaced by the contextual Browse selection).
  Compare matrix          the compare op's result UI; reachable from a marked
                          set in Browse AND from the Node Hub.
```

### Confirmed design decisions (levers settled during the brainstorm)
- **Node-action trigger:** `Enter` → Node Hub on the Detail tab; `A` → the
  Operations dialog contextual to the current selection. **No** auto-open on
  mere cursor movement (avoids modal-spam).
- **Operations naming:** the contextual ops surface is called **"Operations"**
  (not "Actions").
- **No separate Actions tab.** Its op-list-wizard folds into the contextual
  Operations dialog.
- **Session ops keep their own tab** — they are session-lifecycle, not
  node-contextual.
- **Browse default view:** graph; the graph⇄list toggle persists per session.
- **Running:** an always-on header status strip (runner state + active-op
  count) **plus** a full Running tab (renamed from Status).
- **Compare:** reachable both from a marked multi-selection in Browse and from
  the Node Hub.
- **Keybindings:** tabs `b` / `s` / `r` (old `s`=Status moves to `r`=Running,
  freeing `s` for Session); `v` toggles Browse view; `space` marks; `Enter`
  opens Node Hub; `A` opens Operations.

## Migration map

| Today | → Target |
|-------|----------|
| Dashboard + Graph tabs | **Browse** (graph⇄list toggle, shared detail) |
| 3× node-detail renderings | one reusable **NodeDetailPanel** |
| Compare tab + `CompareNodeSelectModal` | **compare op** in the contextual Operations dialog (marked set) |
| Actions tab (design ops + wizard) | **Operations contextual dialog** + seeded wizard |
| `NodeActionSelectModal` (`A`) | the unified **Operations dialog** (extended with multi-node ops) |
| Session ops (were in the wizard) | **Session** tab |
| Status tab | **Running** tab + header strip |
| `NodeDetailModal` (Enter) | **Node Hub ▸ Detail** |

## Proposed child-task decomposition (planning finalizes)

A dependency-ordered split that maximizes early testability:

1. Extract a reusable **NodeDetailPanel** widget (DRY the 3 detail renderings).
   *Foundation, low risk, independently testable.*
2. Merge Dashboard+Graph → **Browse** surface: graph⇄list toggle (graph
   default + per-session persist), shared NodeDetailPanel.
3. **Multi-select** in Browse (`space`-mark) + a selection model.
4. Unified **Operations dialog**: extend `NodeActionSelectModal` with the
   design ops and multi-node ops; drive enable/disable via `op_states` by
   selection cardinality; shorten the wizard (drop its node-pick step); fold in
   the old Actions-tab op list with descriptions.
5. **Compare** as the compare-op result overlay (from marked set / Node Hub);
   drop the Compare tab.
6. **Node Hub** overlay (Enter): Detail + an Operations entry.
7. Split the **Session** tab out of the wizard; **rename Status → Running** and
   add the header status strip.
8. Footer/keybinding deconflict (`b/s/r`, `v`, `space`), CSS, docs
   (`aidocs/framework/tui_conventions.md` + website TUI list/pages), and
   regenerate goldens / update tests.

## Implementation notes
- Reuse existing patterns rather than inventing: `NodeActionSelectModal`
  already implements the op-list + `op_states` (disabled-with-reason) pattern;
  the wizard already has a pure, unit-tested step model
  (`tests/test_brainstorm_wizard_steps.py`) — extend, don't rewrite.
- The wizard currently mounts into `#actions_content` via ~20 query sites;
  re-hosting it (seeded from the contextual selection) is the heaviest child.
- Follow `aidocs/framework/tui_conventions.md` and `tmux_gateway.md`. Keep
  `brainstorm` in the user-facing TUI list (board, monitor, minimonitor,
  codebrowser, settings, brainstorm).

## Coordination (not folded — kept separate per decision)
- **t919** (redesign brainstorm proposal/module UIs from t423): strong overlap
  — both rewrite `brainstorm_app.py` UI. Coordinate sequencing to avoid
  conflicts; the salvageable-ideas work from t423 should land consistently with
  this IA.
- **t535** (status tab agent actions: kill/cleanup/retry): targets the tab this
  task renames to **Running** — implement those agent-management actions within
  the new Running surface.
- **t569** (child-split op) and **t499** (parallel-planning / feedback ops): new
  *operations* that should slot into the new contextual **Operations dialog**
  once it exists.
- **t1018** (op restart / double-click open / footer binding hygiene):
  `depends: [983]` — sequenced **behind** this task so its operation-restart
  action and brainstorm-wide footer binding rework build on the landed
  Running surface and contextual dialogs. Its footer-hygiene child overlaps
  **t983_9** (running_strip_deconflict); land them consistently.
