---
Task: t998_minimonitor_sibling_dialogs_narrow_pane.md
Worktree: (none — profile 'fast', current branch)
Branch: main
Base branch: main
---

# Plan — Fix narrow-pane rendering of minimonitor next-sibling dialogs (t998)

## Context

In `ait minimonitor`, the **`n` (Next)** shortcut opens `NextSiblingDialog`,
and its *Choose sibling* button then opens `ChooseSiblingModal`. Both modals
live in `.aitask-scripts/monitor/monitor_shared.py` and are **shared** with the
full monitor (`monitor_app.py`). They use `width: 70%` and a **horizontal**
button row.

The minimonitor's companion pane is sized to `target_width` (default **40
cols**, `minimonitor_app.py:1217`). At 40 cols, `70%` ≈ 28 cols, minus
`padding: 1 2` ≈ 24 usable. `NextSiblingDialog` has **three** buttons in a
horizontal row (`Pick t<id>`, `Choose sibling`, `Cancel`) needing ~40+ cols —
so buttons are clipped / not all visible. `ChooseSiblingModal` shares the same
`70%` width problem. The full monitor (wide terminal) renders both fine today.

**Goal:** make both dialogs render correctly inside the ~40-col minimonitor
pane, **without changing how they look in the full monitor**.

## Approach

Scope the fix to the narrow context with an opt-in `narrow` flag, so the full
monitor is byte-for-byte unchanged. Textual `DEFAULT_CSS` is class-level, so we
vary behavior via a `narrow` CSS class toggled per-instance — the standard
Textual pattern for instance-conditional styling.

### 1. `NextSiblingDialog` — `monitor_shared.py` (~line 250)

- Add `narrow: bool = False` to `__init__`; store `self._narrow`.
- In `compose()` (or `on_mount`), `if self._narrow: self.add_class("narrow")`.
- Add narrow-scoped CSS overrides to `DEFAULT_CSS`:
  ```css
  NextSiblingDialog.narrow #next-sib-dialog { width: 90%; min-width: 30; }
  NextSiblingDialog.narrow #next-sib-buttons { layout: vertical; height: auto; }
  NextSiblingDialog.narrow #next-sib-buttons Button { width: 1fr; margin: 0 0 1 0; }
  ```
  Vertical full-width buttons guarantee all three render regardless of pane
  width (3 buttons cannot fit horizontally in a 40-col pane at any dialog
  width). The base (non-narrow) CSS is untouched → full monitor unchanged.

### 2. `ChooseSiblingModal` — `monitor_shared.py` (~line 374)

- Same `narrow: bool = False` constructor param + `add_class("narrow")`.
- Narrow-scoped CSS:
  ```css
  ChooseSiblingModal.narrow #choose-sib-dialog { width: 90%; min-width: 30; }
  ```
  Its `OK` / `Cancel` row is only two short buttons (~18 cols incl. margins),
  which fits within the widened narrow dialog — keep them horizontal. The
  scrollable `#choose-sib-list` and help line already flex to width.

### 3. Opt in from the minimonitor — `minimonitor_app.py`

- Line ~854: `NextSiblingDialog(..., parent_id, narrow=True)`.
- Line ~881: `ChooseSiblingModal(payload, siblings, narrow=True)`.

The full monitor's push sites (`monitor_app.py:1609`, `:1644`) are left as-is
(default `narrow=False`).

## Precedent followed

`KillConfirmDialog` (`monitor_shared.py:167-183`) was already adapted for narrow
panes in t994/t995 (`width: 80%; min-width: 28; Button { width: auto; min-width:
10 }`). This task extends the same narrow-pane treatment to the two sibling
dialogs — but via an explicit `narrow` flag so the *shared* full-monitor surface
is provably untouched (kill dialog applied it unconditionally because its 2 short
buttons fit horizontally everywhere; the 3-button next-sibling dialog cannot).

## Rejected alternative

*Apply vertical buttons / wider width unconditionally* (like the kill dialog):
simpler, but it changes the full monitor's polished horizontal layout for a
screen this task isn't about — unnecessary blast radius on a shared class. The
`narrow` flag keeps the change provably scoped.

## Files to modify

- `.aitask-scripts/monitor/monitor_shared.py` — `NextSiblingDialog` +
  `ChooseSiblingModal` (constructor flag, `add_class`, narrow CSS).
- `.aitask-scripts/monitor/minimonitor_app.py` — pass `narrow=True` at the two
  push-screen sites.

## Verification

- **Live check (primary):** Launch `ait minimonitor` docked to a window running
  a child-task agent (e.g. `t983_2`). Press `n`:
  - `NextSiblingDialog` shows the header, details, and **all three** buttons
    (`Pick t…`, `Choose sibling`, `Cancel`) fully within the ~40-col pane.
  - Press *Choose sibling* → `ChooseSiblingModal` shows header, context line,
    scrollable sibling rows, help line, and `OK`/`Cancel` correctly in the
    narrow pane.
- **No regression:** Open the same dialogs in the full `ait monitor` (wide
  window) and confirm the horizontal 70% layout is unchanged.
- **Import/compile sanity:** `python3 -c "import ast,sys;
  ast.parse(open('.aitask-scripts/monitor/monitor_shared.py').read())"` and the
  same for `minimonitor_app.py` (no test harness exists for these modals).

## Step 9 (Post-Implementation)

Per task-workflow: review/commit (`bug: ... (t998)`), then archive via
`./.aitask-scripts/aitask_archive.sh 998` and push. No branch/worktree (profile
`fast`, current branch).

## Risk

### Code-health risk: low
- Change is confined to two CSS blocks + two constructor params + two call-site
  kwargs; the `narrow` class-scoping leaves the shared full-monitor surface
  provably unchanged. · severity: low · → mitigation: TBD

### Goal-achievement risk: low
- Final fit depends on exact label widths vs. the ~40-col pane; mitigated by
  vertical full-width buttons (no horizontal 3-button packing) and a live visual
  check in the verification step. · severity: low · → mitigation: TBD

## Final Implementation Notes
- **Actual work done:** Added an opt-in `narrow: bool = False` constructor param to `NextSiblingDialog` and `ChooseSiblingModal` in `.aitask-scripts/monitor/monitor_shared.py`. Each toggles a `narrow` CSS class in `compose()`. Narrow-scoped `DEFAULT_CSS` overrides widen both dialogs (`width: 90%; min-width: 30`) and stack `NextSiblingDialog`'s three buttons vertically (`layout: vertical; Button { width: 1fr }`). The minimonitor opts in by passing `narrow=True` at the two `push_screen` sites in `minimonitor_app.py` (NextSiblingDialog ~L855, ChooseSiblingModal ~L881).
- **Deviations from plan:** None. Implemented exactly as planned.
- **Issues encountered:** Headless Textual CSS validation isn't possible standalone — `DEFAULT_CSS` references app theme vars (`$surface`, `$warning`) that resolve only inside a running App, so a standalone `Stylesheet.parse()` raises `UnresolvedVariableError` on the pre-existing CSS (false positive). Verified instead via AST parse + import/construct (narrow defaults to False; True only at minimonitor sites) and deferred the visual render check to the live minimonitor pane, which the user confirmed during Step 8 review.
- **Key decisions:** Chose an explicit `narrow` flag over applying the change unconditionally (as `KillConfirmDialog` did) so the *shared* full-monitor surface is provably unchanged — `KillConfirmDialog`'s 2 short buttons fit horizontally everywhere, but the 3-button next-sibling dialog cannot fit in a ~40-col pane at any dialog width, forcing the vertical stack only in the narrow context.
- **Upstream defects identified:** None
