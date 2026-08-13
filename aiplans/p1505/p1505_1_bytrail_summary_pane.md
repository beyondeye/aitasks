---
Task: t1505_1_bytrail_summary_pane.md
Parent Task: aitasks/t1505_lite_trail_mode_and_trail_summary_pane.md
Sibling Tasks: aitasks/t1505/t1505_2_trail_detail_modal_entry_first.md, aitasks/t1505/t1505_3_trail_narrative_overview_field.md, aitasks/t1505/t1505_4_trail_skill_lite_default.md
Archived Sibling Plans: aiplans/archived/p1505/p1505_*_*.md
Worktree: (current branch — profile 'fast')
Branch: (current branch)
Base branch: main
Output branch: main
---

# p1505_1 — By-Trail summary pane

Adds a fixed-height pane at the bottom of the By-Trail view showing the trail's
free-form summary, plus a key that expands it into a modal. Riskiest surface of
t1505 and deliberately sequenced first; no dependency (t1468_5 does not touch
`aitask_board.py`).

## Pre-phase (risk mitigations)

### characterize_board_compose_layout

Before mounting anything, pin the **composited** first row of the footer at a
small terminal size with the board in By-Trail.

- Add to `tests/test_board_bytrail_view.py`, extending `ByTrailTestBase`.
- Use a pilot run (`async with app.run_test(size=(80, 24))`) and assert against
  what actually reaches the screen — a composited strip — not `widget.display` /
  `widget.visible`.
- Rationale, recorded in the board's own CSS at `aitask_board.py:7362` (t1278):
  two same-edge docked siblings land at the **same offset**; one paints over the
  other while both still report `display=True`, `visible=True` and a correct
  region. That defect hid every `sub_title` write for the app's entire history.
  A `display`/`visible` assertion cannot see it.
- Run it **before** step 1 and confirm it passes against the unmodified board —
  a characterization test that was never green on the old code pins nothing.

### label_trail_depth

Read `rendering_hints.depth` (written later by t1505_4) and surface it on the
trail banner / selector row.

- Absent hint → render **nothing**. Never default to "deep": every trail written
  before t1505_4 has no hint, and defaulting would state a falsehood about them.
- The banner is written by `_refresh_subtitle` (`aitask_board.py`), which is the
  documented single writer for the subtitle — add it there, not at a new site.

## Implementation steps

### 1. Pure resolver

In the `# --- Implementation trails ---` helper block (~`aitask_board.py:609`,
next to `build_trail_lanes`, `trail_entry_refs`, `canonical_trail_ref`):

```python
def trail_summary_text(doc) -> str:
    """The trail's free-form summary for the By-Trail pane.

    Prefers `narrative.overview` (t1505_3's advisory prose field) and falls back
    to the always-required `narrative.recommendation_summary`, so a trail written
    before that field existed still shows something useful. Returns "" when
    neither carries text — the caller hides the pane rather than showing an empty
    frame."""
```

Pure and import-testable: no widget, no app state. Whitespace-only is empty at
every level.

### 2. `TrailSummaryPane`

`VerticalScroll` (id `#trail_summary`) holding a `Static`. CSS in the board's
`DEFAULT_CSS`:

```
#trail_summary { height: 6; border-top: hkey $secondary-background; padding: 0 1; }
```

**Never `dock: bottom`.** Textual's `Footer` sets it and `MultiRowFooter`
overrides only `layout`/`height`, so the bottom edge is already claimed. As a
flow child yielded in `compose()` (~`:7964`) after `#board_container` (no
explicit height rule → `1fr`) and before the footer, the pane takes its fixed
rows and the columns keep the rest.

### 3. Visibility — one writer

`display = (base_filter == "bytrail" and trail_summary_text(doc))`.

Drive it from the seam that already owns view state, mirroring the discipline
`_refresh_subtitle` documents. View switch, trail reload, drift callback and
trail selection must all converge on that one writer — **do not** set `display`
from four call sites. Leaving By-Trail must restore the full-height column area.

### 4. Expand key

```python
Binding("v", "trail_summary_expand", "Summary"),
```

`v` is free at App level — the `v`/`u` bindings at `:5819`/`:5833` are
`board.detail` scope (`TaskDetailScreen`). Resolve via `resolve_key("board", …)`
like the other trail actions.

- Gate in `check_action` to By-Trail with a non-empty summary.
- **Re-check the same condition inside `action_trail_summary_expand`.** A binding
  gate is not an action guard: the action stays reachable via the command
  palette, a remap, or a race with a view switch.
- `TrailSummaryScreen(ModalScreen)`: full text in a `VerticalScroll`, `escape` to
  close, modeled on `TrailDetailScreen` (`:3825`).

## Verification

- `bash tests/run_all_python_tests.sh --test-dir tests` — read only the **last**
  line (`PYTHON SUITE: PASSED|FAILED (runner=…, exit=N)`); piping discards the
  exit status, so use `set -o pipefail` or `${PIPESTATUS[0]}`.
- Resolver: `overview` preferred; falls back to `recommendation_summary`; `""`
  when both missing/blank; whitespace-only treated as empty.
- Pane present in By-Trail; **absent** in `all` and `bytopic`; absent in By-Trail
  when the summary is empty.
- **Render-level:** the footer's first row is still composited and readable with
  the pane mounted, at a small terminal size — the assertion the pre-phase pins.
- Expand key opens the modal in By-Trail. **Negative control:** `v` in the `all`
  view does nothing, and calling `action_trail_summary_expand` directly outside
  By-Trail is a no-op.
- Depth label: shown when `rendering_hints.depth` is present; **nothing** rendered
  when absent (assert absence explicitly — a missing label and a "deep" label must
  not be conflated).
- Live check in a real terminal (not only `run_test`): enter By-Trail, confirm the
  pane renders below the columns with the footer fully visible, and that leaving
  the view restores the full column height.

**Trail artifact availability:** t1468_5's bump to schema `1.1.0` invalidates both
stored artifacts until t1468_7 refreshes them. `ERROR:invalid_trail` on those
handles is **expected**, not a defect of this child — use a fixture trail for the
tests and a refreshed trail for the live check.

Post-implementation cleanup, archival and merge follow **Step 9** of the shared
task workflow.
