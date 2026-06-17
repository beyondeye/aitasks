---
priority: medium
effort: high
depends: [983]
issue_type: enhancement
status: Ready
labels: [brainstorming, tui, ait_brainstorm]
created_at: 2026-06-17 10:27
updated_at: 2026-06-17 10:27
boardidx: 130
---

Fix three UX gaps in the `ait brainstorm` TUI
(`.aitask-scripts/brainstorm/brainstorm_app.py`, ~7,900 lines; graph view in
`brainstorm_dag_display.py`; operation model in `brainstorm_session.py` /
`brainstorm_schemas.py`). Surfaced while a `synthesize_001` operation aborted
into a failed state on the Status tab with no recovery path.

This is an umbrella task — **split into the three children below at planning
time** (each independently testable; see
`aidocs/framework/testing_conventions.md` and
`aidocs/framework/tui_conventions.md`).

## Coordination (read first)
- **depends: [983].** t983 is an in-flight IA redesign of this same file that
  collapses 5 tabs → 3, **renames the Status tab → Running**, and moves ops into
  contextual dialogs (children t983_8 session_tab_split, t983_9
  running_strip_deconflict_docs, t983_11 wizard_rehost_actions_screen). Build
  the restart action and footer rework on t983's **landed** surfaces to avoid
  conflicting edits to brainstorm_app.py. A reverse coordination pointer should
  be added to t983.
- **t535** (brainstorm Status tab agent actions — kill/cleanup/retry an
  individual *agent* row) is adjacent but distinct: t535 is **agent-level**,
  child 1 here is **operation/group-level**. Sequence so both land on the same
  (post-t983) Running surface without clobbering each other.

## Child 1 — Operation-level restart on the Status/Running tab
Operations (e.g. `synthesize_001`) are groups in `br_groups.yaml` with terminal
states `Error` / `Aborted` (`brainstorm_schemas.py` GROUP_OPERATIONS;
`brainstorm_session.py` update_operation). Today the only recovery surfaces are
`ctrl+r` / `ctrl+shift+x` / `ctrl+shift+y`, which retry only the
**apply-of-output** step (gated on the agent having already emitted complete
output), and `w`, which resets a single *agent* in Error state. There is **no
operation-level restart** — an operation that aborted before producing output
is stuck.

Add, on the focused operation/group row, **two distinct actions** offered as a
choice:
- **Re-run whole operation fresh** — reset the group to a clean state and
  relaunch its agents from scratch.
- **Retry only the failed step** — resume/re-apply just the part that failed
  (extend the existing retry-apply surfaces).
Confirm destructive re-runs with a modal. Prefer shelling out to existing
`ait crew` / `ait brainstorm` commands over duplicating mutation logic. Add a
footer-visible binding (coordinate with child 3).

**Caveat — the existing `ctrl+shift+x` / `ctrl+shift+y` retry-apply bindings are
themselves undeliverable** (same root cause as child 3 below): they cannot be
pressed through the terminal→tmux→Textual stack. Do **not** model the new
restart binding on them — pick a deliverable, per-screen key per child 3's
guidance. Surfacing these retry actions on the operation/group row (where they
are footer-visible and reachable) is part of fixing recovery.

## Child 2 — Double-click to open operation/node detail
The detail view (`OperationDetailScreen`) opens only via `o` on a node row
(`action_open_operation`); `Enter` on a Status group row only expands/collapses
it. `OperationRow` has a single-click `on_click`; `NodeRow` has none; the graph
`_handle_click` only focuses a node. **No double-click handler exists.** Add
double-click → open detail on the operation/node rows (Textual `events.Click`
carries a `chain` count for click multiplicity), matching the `Enter`/`o`
behavior on each surface.

## Child 3 — Per-screen footer binding hygiene (brainstorm-wide)
General problem across `ait brainstorm`, not just the Status tab. Almost all
bindings are declared globally at the App level and merely *hidden* per-context
via `check_action()` (returns `None` = hidden-but-still-live). Several are not
gated at all (e.g. `ctrl+r` "Retry initializer apply"), so they leak into the
footer of screens where they are irrelevant.

Make contextual shortcuts **genuinely scoped to the screen/tab that owns them**
— bound and unbound with the active surface — rather than global-declared and
selectively suppressed. Idiomatic Textual approaches: move bindings onto the
owning Screen/widget BINDINGS, and/or extend `check_action()` coverage so every
leaking action is gated. Honor the footer-coverage rule and the
`check_action` / `priority` query-scope gotchas documented in
`aidocs/framework/tui_conventions.md`. Coordinate closely with t983_9
(running_strip_deconflict) since both touch the footer/binding surface.

### Motivating case + delivery root cause (t1017 exploration)
The lack of true contextual shortcuts is **why** brainstorm reached for
`ctrl+shift+<letter>` chords in the first place — keys could not be reused
per-screen, so the config-step preview actions were given globally-unique
chords. Those chords are not just hygiene noise; **they are undeliverable**:
- `brainstorm_app.py:3849-3850` binds `ctrl+shift+b` → `cycle_preview_ratio`
  (preview width) and `ctrl+shift+l` → `toggle_preview_numbered` (line
  numbers). Both are footer-visible and correctly gated to the Actions tab +
  `ProposalPreviewPane`, yet pressing them does nothing.
- Root cause is **key delivery, not the app**. Textual's parser is fine — fed a
  real CSI-u sequence (`ESC[98;6u`) it names the key `ctrl+shift+b` and the
  action fires. But through the real ghostty → tmux → Textual stack the legacy
  CSI-u / modifyOtherKeys path collapses `Ctrl+Shift+<letter>` to the same
  control byte as `Ctrl+<letter>`, dropping Shift before Textual ever sees it:
  - `Ctrl+Shift+B` → `Ctrl+B`, which is tmux's secondary prefix
    (`prefix2 C-b`) → tmux swallows it; the app receives nothing.
  - `Ctrl+Shift+L` → `Ctrl+L` → reaches the app but matches no binding (only
    `ctrl+shift+l` is registered) → no-op.
- These (plus `ctrl+shift+x` / `ctrl+shift+y`, child 1) are the **only**
  `ctrl+shift+letter` bindings in the framework; every other TUI uses plain
  keys.

**Implication for this child:** once shortcuts are genuinely per-screen, the
preview actions can move to simple deliverable keys (active only on that screen,
so reuse is fine) — e.g. plain letters where no TextArea has focus, or
`alt+<letter>` (ESC-prefixed, non-printable so a focused TextArea ignores it,
reliably distinguishable across terminals) where typing is possible. **Avoid**
bare `ctrl+b` (tmux prefix) and any `ctrl+shift+<letter>` chord. Treat removing
the dead `ctrl+shift+*` bindings as part of the rework.

**Test-gap to close:** `tests/test_brainstorm_proposal_preview.py` exercises the
action methods (`_apply_preview_ratio`, `action_*`) **directly** and never
drives the key-dispatch path, so the undeliverable bindings passed CI. Add a
real `pilot.press(...)` test for the replacement keys, plus a live-stack manual
verification (the headless Textual driver delivers chords the real terminal
stack cannot, so it cannot catch this class of bug on its own).

## Notes
- Read `aidocs/framework/tui_conventions.md` and
  `aidocs/framework/tmux_gateway.md` before editing the TUI.
- Each child owns its tests; pull out headless-testable units (operation
  state-transition / restart logic) early rather than deferring to a final
  child.
