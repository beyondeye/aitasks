---
priority: high
effort: medium
depends: []
issue_type: feature
status: Ready
labels: [aitask_board, tui, trails, artifacts]
gates: [risk_evaluated]
anchor: 1210
created_at: 2026-08-13 12:26
updated_at: 2026-08-13 12:26
---

## Context

Parent: **t1505** — make `/aitask-trail` cheap enough to actually use, and make
its reasoning readable without a board round-trip. Read the parent plan
`aiplans/p1505_lite_trail_mode_and_trail_summary_pane.md`.

This child adds the **bottom summary pane** to the By-Trail view. It is the
riskiest surface in the parent (Textual layout with a failure mode that is
invisible to `display`/`visible` assertions), so it is sequenced **first** and
carries no dependency — it touches only `aitask_board.py`'s trail UI, which the
in-flight t1468_5 does not edit.

**Why a pane at all:** the trail's prose reasoning currently lives only inside
`TrailDetailScreen`, one card at a time. The user's actual question — "which task
should I pick next, and why?" — is answered by the trail-level summary, which
should be visible *while scanning the cards*, not behind a modal.

## Pre-phase (risk mitigations — do this FIRST)

**`characterize_board_compose_layout`.** Before mounting anything, add a
characterization test that pins the **composited** first row of the footer at a
small terminal size, with the board in the By-Trail view.

This is not ceremony. The board's own CSS comment at `aitask_board.py:7362`
records t1278: Textual places two same-edge docked siblings at the **same
offset**, so one silently paints over the other while both still report
`display=True`, `visible=True` and a correct region — and that hid every
`sub_title` write for the app's whole history. A `display`/`visible` assertion
cannot catch it. Only a render-level check of what actually reaches the screen
can. Pin it before the change, so the pane's regression fails loudly.

**`label_trail_depth`.** Surface `rendering_hints.depth` (written by t1505_4) on
the trail banner/selector so a lite artifact is never silently mistaken for a
deep one. **An absent hint renders nothing — never "deep".** Every pre-t1505_4
trail has no hint, and defaulting would state a falsehood about them.

## Key files to modify

- `.aitask-scripts/board/aitask_board.py`
  - `AitaskBoard.compose()` (~line 7964) — yield the pane after
    `#board_container` and before the footer.
  - The board's `DEFAULT_CSS` block (~line 7290-7400) — pane styling.
  - `BINDINGS` (~line 7560-7655) — the expand key.
  - `check_action()` — gate the expand key to By-Trail.
  - `_render_bytrail` / `refresh_board`'s `bytrail` branch / `_refresh_subtitle`
    — pane visibility and the depth label.
  - The trail helper block (~line 609-1020) — the pure resolver.
- `tests/test_board_bytrail_view.py` — tests (extends `bf.FixtureBoardTestBase`
  via `ByTrailTestBase`).

## Implementation plan

### 1. Pure resolver (do this first — it is independently testable)

Next to the other pure trail helpers (`build_trail_lanes`, `trail_entry_refs`,
`canonical_trail_ref`, all in the `# --- Implementation trails ---` block from
~line 609), add:

```python
def trail_summary_text(doc) -> str:
    """The trail's free-form summary for the By-Trail pane.

    Prefers `narrative.overview` (t1505_3's advisory prose field) and falls back
    to the always-required `narrative.recommendation_summary`, so a trail written
    before that field existed still shows something useful. Returns "" when
    neither carries text — the caller hides the pane rather than showing an empty
    frame."""
```

Whitespace-only values count as empty at every level. Keep it pure and
import-testable — no widget or app state.

### 2. `TrailSummaryPane`

A `VerticalScroll` (id `#trail_summary`) holding a `Static`. CSS:

```
#trail_summary { height: 6; border-top: hkey $secondary-background; padding: 0 1; }
```

**NEVER `dock: bottom`.** The footer already docks there (Textual's `Footer`
sets `dock: bottom`; `MultiRowFooter` overrides `layout`/`height` but does not
unset the dock). A docked pane is the exact t1278 collision the pre-phase test
guards. As a flow child yielded after `#board_container` (which has no explicit
height rule and so resolves to `1fr`), the pane takes its fixed rows and the
columns keep the rest.

### 3. Visibility

`display = (base_filter == "bytrail" and trail_summary_text(doc))`. Drive it from
the seam that already owns view state, following the single-writer discipline
`_refresh_subtitle` documents ("All subtitle updates … route through here, so
leaving By-Trail restores the auto-refresh text"). The same must hold here:
**leaving By-Trail must restore the full-height column area.** A view switch, a
trail reload, a drift callback and a trail selection must all converge on the
same writer — do not set `display` from four places.

### 4. Expand key

```python
Binding("v", "trail_summary_expand", "Summary"),
```

`v` is free at App level — the `v`/`u` bindings at `aitask_board.py:5819`/`5833`
belong to the `board.detail` scope (`TaskDetailScreen`), not the app. Resolve
through `resolve_key("board", …)` like the other trail actions.

Gate it in `check_action` to By-Trail with a non-empty summary, **and re-check
the same condition inside `action_trail_summary_expand`**. A binding gate is not
an action guard: `check_action` controls footer visibility and dispatch, but the
action is still reachable (command palette, a remapped key, a race with a view
switch) — re-check inside the action body.

`TrailSummaryScreen(ModalScreen)` renders the full text in a `VerticalScroll`,
`escape` to close, modeled on `TrailDetailScreen` (~line 3825).

## Reference files for patterns

- `TrailDetailScreen` (`aitask_board.py:3825`) — modal shape, `DEFAULT_CSS`,
  `escape` binding, `Static` in a `VerticalScroll`.
- `_refresh_subtitle` — the single-writer pattern this pane's visibility copies.
- `_trail_drift_text` (`:3392`) — a small pure text helper with a docstring
  explaining its truncation budget; `trail_summary_text` should read the same way.
- The `#filter_area` CSS comment (`:7362`) — the t1278 write-up.

## Verification steps

- `bash tests/run_all_python_tests.sh --test-dir tests` — read only the LAST
  line (`PYTHON SUITE: PASSED|FAILED (runner=…, exit=N)`). Piping discards the
  exit status; use `set -o pipefail` or `${PIPESTATUS[0]}`.
- Resolver unit tests: `overview` preferred; fallback to
  `recommendation_summary`; `""` when both are missing/blank; whitespace-only
  treated as empty.
- Pilot test: pane present in By-Trail, **absent** in `all` and `bytopic`, and
  absent in By-Trail when the summary is empty.
- **Render-level:** the footer's first row is still composited and readable with
  the pane mounted, at a small terminal size. This is the assertion the pre-phase
  characterization pins — a `display`/`visible` check is not a substitute.
- Expand key: `v` opens the modal in By-Trail; **negative control** — `v` in the
  `all` view does nothing, and `action_trail_summary_expand` called directly
  outside By-Trail is a no-op.
- Live check in a real terminal (not only `run_test`): enter By-Trail, confirm
  the pane renders below the columns with the footer fully visible, and that
  leaving the view restores the full column height.

**Trail artifact availability:** t1468_5 bumps the trail schema to `1.1.0` and
invalidates both stored artifacts until t1468_7 refreshes them. If the stored
handles report `ERROR:invalid_trail`, that is **expected** and is not a defect of
this child — use a fixture trail for the tests, and refresh a real trail (or wait
for t1468_7) for the live check.
