---
Task: t1247_board_filter_row_adaptive_width_and_reflow.md
Base branch: main
plan_verified: []
---

# t1247 — Board filter row: adaptive width and reflow

## Context

In `ait board`, the base-filter row at the top (`[a All | l Locked | f Free |
i In-Flight | y · By-Topic | z · By-Trail]   g Git   t Type`) is visibly cut
off, and the search box appears to sit on top of the missing segments.

**Root cause (measured against the real `ViewSelector`, not a replica):**
`.aitask-scripts/board/aitask_board.py:5227` declares `#view_col { width: 78; }`
— a hardcoded column count. `#view_selector` is a `Static` with no width rule,
so it fills its parent (78) and its 88-cell line is truncated there. The search
box, already flexed by the global `Input { width: 1fr; }` (`:5232`), begins
exactly at the truncation point.

Probe of the production `ViewSelector` with the board's real keybindings
registered, at a 140-col terminal:

| CSS | `#view_col` | selector content | search alloc | truncation |
|---|---|---|---|---|
| current `width: 78` | 78 | 76 | 62 | **12 cells lost** |
| `width: auto` | 90 | 88 | 50 | **0** |

`git log -L 5227,5227` shows this width has been hand-bumped on *every* prior
filter addition — 26 (t273) → 36 (t645) → 48 (t850) → 62 (t635_9) → 78 (t1016_4,
By-Topic) — and commit `03eade720` (t1210_4, By-Trail) added a sixth base filter
without bumping it. The number is *also* invalidated by key rebinds: the `?`
shortcut editor can change a key, and `render_label(style="leading")` emits
`k text` when the key matches the first letter but `k · text` (+2 cells)
otherwise. **The fix must derive the geometry, not bump the constant.**

Intended outcome: the filter row is never truncated again — by a new filter, by
a rebind, or by a narrow terminal — and the search box adapts, reflowing onto
its own line rather than squeezing the filters.

## Approach

Three coordinated changes, all in `.aitask-scripts/board/aitask_board.py`.

### 1. Single source of truth for the selector's width

`ViewSelector.render()` (`:1454-1495`) already computes the exact cell width in
its `col` counter — that arithmetic drives `_click_targets` for `on_click`
hit-testing. Extract it so layout and hit-testing read the *same* number.

Refactor the body of `render()` into a pure helper returning
`(markup, targets, width)`, then:

```python
def content_width(self) -> int:
    """Rendered width in terminal cells. Pure — no app or mount required."""
    return self._build()[2]

def render(self) -> str:
    markup, targets, _ = self._build()
    self._click_targets = targets
    return markup
```

Use `rich.cells.cell_len` for segment widths rather than `len()`. Today they
agree (`·` is a 1-cell glyph, total 88 either way), but a future wide-glyph
label would silently desync layout from hit-testing.

`content_width()` being pure is what makes the regression test a plain unit
assertion with no running app — matching `test_brainstorm_dag_op_badge.py:127`,
which imports the width constant from the production module so it cannot drift.

### 2. Auto-width column + reflow (CSS)

Replace the fixed width at `:5226-5232`:

```
#filter_area { dock: top; height: auto; margin: 0 0 1 0; }
#filter_area.narrow { layout: vertical; }
#view_col { width: auto; height: auto; }
#filter_area.narrow #view_col { width: 100%; }
#view_selector { height: 1; padding: 0 1; width: auto; }
#search_box { width: 1fr; min-width: 30; }
```

Keep the global `Input { width: 1fr; }` untouched — the `#search_box` ID rule
wins on specificity and leaves every dialog `Input` alone.

The `.narrow` class flipping a container to `layout: vertical` is an existing,
blessed pattern (`monitor/monitor_shared.py:297-303`, `:327-328`); it is simply
never wired to a resize today.

### 3. Resize handler (the reflow trigger)

The board has **zero** resize handling in 8409 lines. Follow the repo
convention — plain `on_resize(self, event)` reading `event.size.width`, with
`query_one` wrapped in try/except (`codebrowser_app.py:676-691`) and a named
class-attr constant (`codebrowser_app.py:405-406`). No debouncing: no handler in
the repo debounces; they use cheap early-exit guards.

```python
FILTER_SEARCH_MIN_WIDTH = 30   # allocation incl. Input border(2) + padding(4)

def _apply_filter_reflow(self, width: int | None = None) -> None:
    try:
        selector = self.query_one("#view_selector", ViewSelector)
        area = self.query_one("#filter_area")
    except Exception:
        return
    width = self.size.width if width is None else width
    if width <= 0:               # pre-layout size; repo-wide idiom
        return
    needed = selector.content_width() + 2 + self.FILTER_SEARCH_MIN_WIDTH
    area.set_class(width < needed, "narrow")

def on_resize(self, event) -> None:
    self._apply_filter_reflow(event.size.width)
```

Call `_apply_filter_reflow()` from `on_mount` (`:5613`) and from
`_refresh_selector` (`:6189`) so a runtime key rebind re-evaluates the threshold.

Threshold with today's labels: `88 + 2 + 30 = 120`. Verified behavior — side by
side at ≥120, reflowed below:

```
term=140 narrow=False view_col=90 search=44   term=113 narrow=True view_col=113 search=107
term=120 narrow=False view_col=90 search=24   term= 80 narrow=True view_col= 80 search= 74
```

### 4. Adjacent drift fix (explicitly flagged — beyond the literal AC)

`_compute_search_placeholder` (`:6223`) hardcodes the string
`"(a/l/f/i/y/z to switch base)"` — the same "hardcoded key list rots on rebind"
defect, one line away. Derive it from `ViewSelector.BASES` + `resolve_key`.
Called out here rather than folded in silently; drop it if you'd rather keep the
change minimal.

## Correction to the task description

The task file claims `#type_filter_summary` "blocks a naive `width: auto`"
because a long `types: …` string would drive the container width. **Probing
disproved this**: the summary has no width rule, so it does not contribute to
auto-width — `#view_col` measured 90 both with an empty summary and with
`types: bug, enhancement, documentation, performance, refactor, style, test,
chore`. No `max-width`, wrap, or relocation is needed. The corresponding
acceptance criterion stays (as a regression guard) but the implementation note
is wrong and will be corrected in the task file.

## Known limit (accepted, not fixed)

When the terminal is narrower than the selector itself (~90 cells), the selector
still clips even in narrow mode. Letting it *wrap* would break `on_click`:
`_click_targets` are 1-D column offsets and `on_click` (`:1497-1509`) ignores
`event.y`, so wrapped segments would dispatch to the wrong filter. Making
hit-testing 2-D is out of scope. Keyboard bindings (`a/l/f/i/y/z`) work
regardless; only click targeting and visibility degrade at that width.

## Files to modify

- `.aitask-scripts/board/aitask_board.py` — `ViewSelector` (`:1454-1495`), CSS
  (`:5226-5232`), `compose`/`on_mount` (`:5593-5616`), `_refresh_selector`
  (`:6189`), `_compute_search_placeholder` (`:6223`).
- `tests/test_board_filter_row_layout.py` — new.
- `aitasks/t1247_*.md` — correct the disproved implementation note.

## Verification

New test file, following `tests/test_board_topic_view.py:22-44` (chdir + path
preamble) and the width-assertion form of
`tests/test_agent_model_picker_narrow.py:141-146`:

1. **Pure unit** — `ViewSelector(...).content_width() == cell_len(render plain)`,
   no app. Pins layout and hit-testing to one number.
2. **Live-surface guard** — boot `KanbanApp` via `run_test(size=(160, 48))`;
   assert `view_col.region.width >= selector.content_width() + 2`, i.e. the
   filters are not truncated. This is the correctness invariant, and it is
   *threshold-independent*.
3. **Negative control** — monkeypatch `ViewSelector.BASES` with an extra
   synthetic filter (and separately, rebind a key to a non-first-letter form so
   a segment widens by 2). Re-boot and assert the guard still holds. Against the
   pre-fix `width: 78` this fails, which is what proves the guard discriminates.
4. **Reflow** — boot at `(160, 48)` and `(100, 48)`; assert `#filter_area` lacks
   / has the `narrow` class and that the search box allocation stays
   `>= FILTER_SEARCH_MIN_WIDTH` in the reflowed layout.
5. **Long type summary** — set a long `types: …` string, re-measure, assert
   `#view_col` width is unchanged.
6. **Click targeting** — assert `on_click` at each segment's midpoint still
   selects the matching base filter, in both layouts.

Run isolated *and* in the full suite — `t1179` documents that
`run_all_python_tests.sh` is order-dependent (modules imported under two names
break `isinstance`):

```bash
python3 -m pytest tests/test_board_filter_row_layout.py -v
bash tests/run_all_python_tests.sh
```

Manual: `ait board`, confirm all six filters plus `g Git` / `t Type` are fully
visible; narrow the terminal below ~120 columns and confirm the search box drops
to its own line instead of eating the filters; click each segment.

## Risk

### Code-health risk: low
- CSS `width: auto` changes the board's top-row geometry, which every other
  widget lays out beneath; a mis-sized filter area would shift the board
  container · severity: low · → mitigation: in-task (verification steps 2 and 4
  measure at multiple terminal widths)
- Refactoring `render()` into `_build()` touches the arithmetic that drives
  `on_click` hit-testing — a silent desync would misroute filter clicks ·
  severity: medium · → mitigation: in-task (verification step 6 asserts click
  dispatch per segment; step 1 pins render width and `content_width()` to one
  source)

### Goal-achievement risk: low
- The reflow threshold (`FILTER_SEARCH_MIN_WIDTH = 30`) is a UX judgement, not a
  correctness invariant, and adds a fourth uncentralized narrow-terminal
  breakpoint to the repo · severity: low · → mitigation:
  centralize_tui_narrow_breakpoint
- Terminals narrower than the selector itself still clip (documented limit
  above); a user on a very narrow terminal may consider the bug unfixed ·
  severity: low · → mitigation: board_selector_wrap_2d_hittest

### Planned mitigations
- timing: after | name: board_selector_wrap_2d_hittest | type: enhancement | priority: medium | effort: medium | addresses: goal-achievement — selector still clips below ~90 cols | desc: Make ViewSelector._click_targets 2-D (row + column, honour event.y) so the filter row can wrap instead of clipping on very narrow terminals.
- timing: after | name: centralize_tui_narrow_breakpoint | type: refactor | priority: low | effort: low | addresses: goal-achievement — narrow-terminal breakpoint drift | desc: Hoist the inline narrow-terminal breakpoints (codebrowser_app.py 120/80, code_viewer.py 80, board FILTER_SEARCH_MIN_WIDTH) into one shared lib constant.

## Step 9 (Post-Implementation)

Standard cleanup, archival, and merge per `task-workflow` Step 9. No worktree was
created (profile `fast`, `create_worktree: false`) — work is on the current
branch, so the merge sub-step is a no-op and archival runs via
`./.aitask-scripts/aitask_archive.sh 1247`.

## Final Implementation Notes

- **Actual work done:** Implemented as planned in
  `.aitask-scripts/board/aitask_board.py` (+87/−11) plus a new 12-test suite
  `tests/test_board_filter_row_layout.py` (285 lines).
  - `ViewSelector._build()` extracted as the single layout pass returning
    `(markup, targets, width)`; `render()` and the new pure `content_width()`
    both consume it. Segment widths switched from `len()` to
    `rich.cells.cell_len`.
  - CSS: `#view_col` `width: 78` → `auto`, `#view_selector` gained
    `width: auto`, and `#filter_area.narrow { layout: vertical }` +
    `#filter_area.narrow #view_col { width: 100% }` added for the reflow.
  - `KanbanApp.FILTER_SEARCH_MIN_WIDTH = 30`, `_apply_filter_reflow()` and
    `on_resize()` added — the board's first resize handling. Called from
    `on_mount` and `_refresh_selector`.
  - `_compute_search_placeholder` now derives the key hint from
    `ViewSelector.BASES` + `resolve_key` instead of the literal
    `"(a/l/f/i/y/z to switch base)"`.

- **Deviations from plan:**
  1. **Dropped the planned `#search_box { min-width: 30 }`.** It duplicated
     `FILTER_SEARCH_MIN_WIDTH`, recreating the very two-sources-of-truth defect
     this task exists to remove. The reflow threshold already guarantees the
     floor (search box gets exactly 30 cells at the boundary, verified), so the
     constant is now the sole source of truth. Compensated by strengthening
     `test_reflow_threshold_tracks_the_selector_width` into an at-bound /
     over-bound assertion on the search-box allocation.
  2. **Kept the flagged adjacent placeholder fix** (plan §4, explicitly offered
     as droppable). Output is byte-identical today (`a/l/f/i/y/z`) and follows
     the table automatically afterwards — verified by injecting an extra base
     and observing `a/l/f/i/y/z/g`.

- **Issues encountered:**
  - The planned blocker "`#type_filter_summary` blocks a naive `width: auto`"
    was **disproved by probing the real widget** during planning: the summary
    carries no width rule so it does not contribute to auto-width. `#view_col`
    measured 90 cells both with an empty summary and with a deliberately
    over-long `types: …` string. No `max-width` / wrap / relocation was needed.
    The task file's implementation note was corrected in place, and
    `test_long_type_summary_does_not_widen_the_column` now guards it.
  - `~/.aitask/venv/bin/python` has no `pytest`; the suite runs under
    `-m unittest` (which is `run_all_python_tests.sh`'s documented fallback).
  - Measured widths are easy to misread: `widget.size.width` is the *content*
    box while `outer_size.width` / `region.width` is the allocation. For the
    search `Input` they differ by 6 (2 border + 4 padding). The tests assert on
    `region` / `outer_size`.

- **Key decisions:**
  - **Derive, don't bump.** The row width is computed from the rendered selector
    rather than hardcoded, so the class of bug (hand-bumped on every filter
    addition: 26 → 36 → 48 → 62 → 78, missed for By-Trail) cannot recur.
  - **One arithmetic site.** Layout width and click hit-testing come from the
    same `_build()` pass — a desync would misroute filter clicks silently.
  - **Correctness separated from UX tuning.** The no-truncation invariant is
    threshold-independent; only the reflow breakpoint depends on
    `FILTER_SEARCH_MIN_WIDTH`. Tests pin the invariant, not the magic number.
  - **Accepted limit:** below ~90 columns the selector still clips. Wrapping it
    would break `on_click`, whose `_click_targets` are 1-D column offsets and
    which ignores `event.y`. Deferred to the confirmed follow-up
    `board_selector_wrap_2d_hittest`.

- **Verification performed:**
  - New suite: 12/12 pass.
  - **Harness proven able to fail:** reverting *only* `width: auto` → `78` makes
    exactly the 5 truncation guards fail with exit 1
    (`78 not greater than or equal to 90`), while the pure-unit and reflow tests
    correctly stay green (they pin different properties). Restored via a
    targeted edit — not `git checkout` — and re-verified green.
  - All board suites after the final change: 63/63 pass.
  - Full python suite: 2111 tests, OK.
  - Measured against the real `KanbanApp`: truncation 0 at 160/130/120/119/100/80
    columns (was 12 cells lost); reflow threshold lands exactly at 120.

- **Upstream defects identified:** None

