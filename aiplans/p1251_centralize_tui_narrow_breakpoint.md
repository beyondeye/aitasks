---
Task: t1251_centralize_tui_narrow_breakpoint.md
Worktree: (none — profile `fast`, `create_worktree: false`; work on current branch)
Branch: main (current branch)
Base branch: main
Output branch: main
---

# t1251 — Centralize the TUI narrow-terminal breakpoint

## Context

t1247 added `KanbanApp.FILTER_SEARCH_MIN_WIDTH = 30` to the board and flagged, in
its own `## Risk` section, that the repo was accumulating uncentralized
narrow-terminal breakpoints with no shared definition of "what counts as a narrow
terminal". This task is the recorded "after" mitigation for that risk.

A full inventory of `.aitask-scripts/` was taken during planning. It shows the
repo has **exactly three** places that ask "is this terminal narrow?", and they
are not all the same kind of thing:

| Site | Form | Kind |
|---|---|---|
| `codebrowser/codebrowser_app.py:683,685` | `width >= 120` / `width >= 80` | **terminal tier breakpoint** |
| `codebrowser/code_viewer.py:280` | `app_width < 80` | **terminal tier breakpoint** |
| `board/aitask_board.py:5860` | `selector.content_width() + 2 + FILTER_SEARCH_MIN_WIDTH` | **derived** — already correct |

The board's threshold is *computed from live widget geometry*, which is the
pattern the rest of the tree should aspire to, not a literal to hoist. Only the
two codebrowser sites hold hard-coded tier literals, and they share the same
`80` boundary while writing it independently.

Everything else that looked like a candidate turned out to be a **component
minimum width** — a property of one widget, not of the terminal. Per the task's
explicit constraint ("do not collapse semantically different numbers into one"),
those stay where they are and get documented rather than moved.

**Outcome:** one shared module owns the *tier decision*; each TUI keeps ownership
of its own per-tier dimensions; behavioral tests pin that each migrated site
reads the shared value; and a cross-referenced convention section records why
every other width constant stayed where it is.

## Scope decision (confirmed with the user)

Centralize **the terminal-width tier breakpoints only**. Explicitly *not* moved:

| Constant | Where it stays | Why |
|---|---|---|
| `CODE_MIN_WIDTH = 80` | `codebrowser_app.py` | Code-pane floor. Numerically equal to the narrow breakpoint **by coincidence**; merging them would couple two independent decisions. |
| `DETAIL_DEFAULT_WIDTH = 30` | `codebrowser_app.py` | Detail-pane default width, not a threshold. |
| `FILTER_SEARCH_MIN_WIDTH = 30` | `aitask_board.py` | Search-box floor. t1247 made it the sole source of truth (deliberately not mirrored into CSS) — moving it would break that property for no gain. |
| `_SENTINEL_SAFE_COLS = 24` | `monitor/concern_parser.py` | Derived from sentinel string lengths (21/18 chars). A *correctness* threshold, not a UX one. |
| `_NARROW_PREFIX_COLS = 8` | `monitor/monitor_shared.py` | Fixed prefix cost of a concern row. |
| `target_width = 40` | `monitor/minimonitor_app.py` | A tmux **pane target width** the app pins itself to, sourced from `tmux.minimonitor.width` config — not a test against the terminal. |
| `narrow: bool` dialog kwarg | `monitor_shared.py`, `agent_command_screen.py`, `agent_model_picker.py`, `tui_switcher.py` | **Not width-derived at all.** `_switcher_narrow()` returns a static `False`, overridden to `True` only by minimonitor. It is a *host-role* flag ("am I in a split pane?"), so it has no breakpoint to share. |

## Implementation

### 1. New file — `.aitask-scripts/lib/tui_layout.py`

A small pure-constants module in the shape of the existing `lib/task_levels.py`
and `lib/launch_modes.py` precedents. `tests/test_no_lib_to_tui_import.sh`
requires `lib/` never import from a TUI dir — a constants module satisfies that
trivially (dependency runs TUI → lib).

```python
"""Canonical terminal-width tiers for aitasks Textual TUIs.

Single Python source of truth for "how wide is this terminal?" — the question a
TUI asks when it picks a layout, not the question a widget asks about itself.

SCOPE — tiers, not component minimums. A *component minimum width* ("this widget
needs N cells to be usable", e.g. KanbanApp.FILTER_SEARCH_MIN_WIDTH or
CodeBrowserApp.CODE_MIN_WIDTH) is a property of that widget and deliberately
stays with it. Do not move such constants here, and do not reuse these tier
values as a component floor just because the numbers happen to match today —
CODE_MIN_WIDTH is 80 by coincidence, not by derivation.

Rationale, the full inventory of constants that deliberately stayed put, and the
rule for adding a new TUI: aidocs/framework/tui_conventions.md, section
"Terminal-width tiers vs component minimum widths".
"""

NARROW_TERMINAL_WIDTH = 80    # below this, a terminal is `NARROW`
WIDE_TERMINAL_WIDTH = 120     # at or above this, a terminal is `WIDE`

NARROW = "narrow"
NORMAL = "normal"
WIDE = "wide"


def terminal_tier(width: int) -> str:
    """Return NARROW / NORMAL / WIDE for a terminal of `width` cells."""
    if width >= WIDE_TERMINAL_WIDTH:
        return WIDE
    if width >= NARROW_TERMINAL_WIDTH:
        return NORMAL
    return NARROW


def is_narrow_terminal(width: int) -> bool:
    """True when `width` falls in the NARROW tier."""
    return terminal_tier(width) == NARROW
```

**Why predicates rather than exported ints.** Consumers import the *functions*,
so the numeric comparison exists at exactly one place in the repo. A function
body resolves its module globals at call time, so patching
`tui_layout.NARROW_TERMINAL_WIDTH` in a test propagates to **every** call site —
which is what lets one behavioral test prove all sites read the shared value.
Exporting bare ints under `from tui_layout import NARROW_TERMINAL_WIDTH` would
bind a copy per module and lose that property.

### 2. `.aitask-scripts/codebrowser/codebrowser_app.py`

`sys.path` already carries `lib` (line 30), so no path plumbing is needed.

- Add `from tui_layout import NARROW, NORMAL, WIDE, terminal_tier` beside the
  existing `from tui_clipboard import ...` (line 34).
- Add a class attr next to `DETAIL_DEFAULT_WIDTH` / `CODE_MIN_WIDTH` (lines
  405–406) mapping tier → the codebrowser's own sidebar width. The per-tier
  dimensions stay owned by the codebrowser; only the tier decision is shared:

  ```python
  SIDEBAR_WIDTH_BY_TIER = {WIDE: 35, NORMAL: 28, NARROW: 22}
  ```

- Rewrite the `on_resize` branch (lines 683–688):

  ```python
  sidebar.styles.width = self.SIDEBAR_WIDTH_BY_TIER[terminal_tier(width)]
  ```

Values are unchanged: 120→35, 80→28, below→22.

### 3. `.aitask-scripts/codebrowser/code_viewer.py`

`sys.path` already carries `lib` (lines 17–19).

- Add `from tui_layout import is_narrow_terminal  # noqa: E402` beside the
  existing `numbered_source_view` / `annotation_data` imports (lines 22–23).
- Name the two gutter widths as class attrs (they are currently bare literals in
  the return statements) and rewrite `_annotation_col_width` (lines 274–282):

  ```python
  ANNOTATION_COL_WIDTH = 12
  ANNOTATION_COL_WIDTH_NARROW = 10

  def _annotation_col_width(self) -> int:
      """Return annotation column width, adjusted for narrow terminals."""
      try:
          app_width = self.app.size.width
      except Exception:
          return self.ANNOTATION_COL_WIDTH
      if is_narrow_terminal(app_width):
          return self.ANNOTATION_COL_WIDTH_NARROW
      return self.ANNOTATION_COL_WIDTH
  ```

Values are unchanged: `<80` → 10, otherwise 12.

### 4. Documentation (the durable guard against literal drift)

There is **no automated literal-reintroduction guard** in this task — that is a
deliberate scope decision (see "Deviation from the task's Verification section"
below). The convention doc *is* the mechanism, so it has to be findable from the
code and vice versa: the two surfaces are **cross-referenced in both
directions**.

- `aidocs/framework/tui_conventions.md` — add a section "Terminal-width tiers vs
  component minimum widths". The file currently has **no** width guidance at all.
  It states the rule (branch on `tui_layout.terminal_tier` /
  `is_narrow_terminal`; never re-derive a tier literal; keep component floors
  with their widget), names `.aitask-scripts/lib/tui_layout.py` as the source of
  truth, and reproduces the "stays put" table from the Scope decision above with
  each constant's file path — so the next author does not re-litigate it.
- `.aitask-scripts/lib/tui_layout.py` — its module docstring points back at
  `aidocs/framework/tui_conventions.md` by path, so someone reading the constants
  finds the rationale, and someone reading the rationale finds the constants.
- `CLAUDE.md` already routes TUI work to `tui_conventions.md` ("Read
  `aidocs/framework/tui_conventions.md` when editing any Textual TUI under
  `.aitask-scripts/`"), so the new section is on the path an agent already
  reads before touching these files. No `CLAUDE.md` change is needed.

## Tests — `tests/test_tui_narrow_breakpoint.py` (new)

Note the coverage gap this closes: `tests/test_code_viewer_render.py` drives every
case at exactly `run_test(size=(80, 24))`, so `app_width < 80` is always False —
the narrow arm of `_annotation_col_width` has **never** been executed by a test,
and `on_resize` has no coverage at all.

Follow the shape of `tests/test_board_filter_row_layout.py` (the gold standard:
drives the real app via `run_test` + Pilot and derives thresholds from the live
widget rather than restating them).

**Layer 1 — unit, tier boundaries.** `terminal_tier` at 79 → `NARROW`, 80 →
`NORMAL`, 119 → `NORMAL`, 120 → `WIDE`; `is_narrow_terminal` agrees with
`terminal_tier` across the same points.

**Layer 2 — behavioral, proves each site reads the shared value.** For each
migrated site: drive the real widget/app, assert the tier-correct result, then
monkeypatch `tui_layout.NARROW_TERMINAL_WIDTH` to a distinctive value (e.g. 200)
and assert the *same* input now produces the narrow result.

- `code_viewer`: reuse the `_HostApp` harness from `test_code_viewer_render.py`.
  At `size=(100, 24)` → `_annotation_col_width() == 12`; at `(70, 24)` → `10`.
  With `NARROW_TERMINAL_WIDTH` patched to 200, `(100, 24)` → `10`, and assert
  explicitly `!= 12` so the test cannot pass by coincidence.
- `codebrowser_app`: boot the real `CodeBrowserApp` (its `__init__` takes no
  required args and performs no I/O) via `run_test` at widths 130 / 100 / 70 and
  assert `sidebar.styles.width.value` is 35 / 28 / 22; then patch
  `NARROW_TERMINAL_WIDTH = 200` and assert width 100 yields 22, not 28.
  *Fallback if `on_mount` proves too heavy to boot headlessly:* call the real
  `CodeBrowserApp.on_resize` on a real instance with a stub sidebar object. This
  still exercises the production method and its module globals — do **not**
  substitute a replica class.

There is no AST/source-scanning layer — see the deviation note below.

**Run both ways** — isolated (`python3 -m pytest tests/test_tui_narrow_breakpoint.py -v`)
and inside `tests/run_all_python_tests.sh`; t1179 records that the full suite is
order-dependent.

### Deviation from the task's Verification section

The task file asks for "a test asserting each migrated call site reads the shared
constant rather than a literal, so a future edit cannot silently reintroduce a
local number." That requirement splits in two, and this plan covers one half by
test and the other by documentation — a deliberate, user-confirmed decision:

- *"each migrated call site reads the shared constant"* — **covered by test.**
  Layer 2's monkeypatch-and-drive assertions fail if a site stops reading
  `tui_layout`'s value.
- *"a future edit cannot silently reintroduce a local number"* — **covered by
  documentation, not by a test.** An earlier draft of this plan added an AST
  scanner (flag `ast.Compare` against an int constant in `{80, 120}`) plus a
  negative control. It was dropped: the guard would police only the two files
  already covered behaviourally, while the actual drift risk is a *new* TUI
  written later — which such a scanner would not see either. The convention
  section in `tui_conventions.md` (reached via the existing `CLAUDE.md` pointer)
  is the mechanism instead.

This is recorded here rather than silently narrowed; the task file's Verification
bullet should be updated to match when the change lands.

## Verification

1. `python3 -m pytest tests/test_tui_narrow_breakpoint.py -v` — new suite passes.
2. `python3 -m pytest tests/test_code_viewer_render.py tests/test_board_filter_row_layout.py -v`
   — existing suites stay green (t1247's filter-row geometry is untouched).
3. `bash tests/run_all_python_tests.sh` — full suite, checking for order effects.
4. `bash tests/test_no_lib_to_tui_import.sh` — the new `lib/` module must not
   violate the import direction.
5. Docs cross-reference is bidirectional: `grep -n tui_layout
   aidocs/framework/tui_conventions.md` and `grep -n tui_conventions
   .aitask-scripts/lib/tui_layout.py` must each return a hit.
6. Manual: run `ait codebrowser`, resize the terminal across ~80 and ~120 cols,
   confirm the sidebar steps 22 → 28 → 35 and the annotation gutter narrows below
   80 exactly as before the refactor. Run `ait board` across its reflow threshold
   to confirm it is unaffected.

## Risk

### Code-health risk: low
- The two migrated call sites are the layout entry points for the codebrowser;
  an off-by-one in `terminal_tier`'s boundary conditions would silently change
  the tier at exactly 80 or 120 cells · severity: low · → mitigation: in-task
  (Layer-1 unit tests pin all four boundary points, and Layer-2 asserts the
  rendered widths at three real terminal sizes)
- Introducing a shared module invites future authors to reuse the tier values as
  component floors, re-coupling the numbers this task just separated ·
  severity: low · → mitigation: in-task (module docstring states the scope rule
  explicitly, and the `tui_conventions.md` section records the "stays put" table)

### Goal-achievement risk: low
- The task text names four call sites, but the inventory shows only two hold
  centralizable literals — the board's threshold is already derived and the
  monitor's `narrow` kwarg is not width-derived at all. A reader of the original
  task may expect more sites to change than actually do · severity: low ·
  → mitigation: in-task (the Scope decision table above records a disposition
  and reason for every site the task named, so nothing is silently dropped)
- Protection against re-introducing a local literal is a **convention document**,
  not an executable check: a future author who does not read
  `tui_conventions.md` can add a fifth uncentralized breakpoint and nothing will
  fail · severity: low · → mitigation: accepted (see below)

**Mitigation decision.** An `after` mitigation
(`tui_narrow_breakpoint_repo_guard` — extend the source guard to a repo-wide
scan) was proposed and initially confirmed during planning. It was then
withdrawn when the AST guard was dropped from this task's scope: a follow-up
task to *extend* a guard that will not exist would be incoherent, and a
repo-wide source scanner is the same mechanism this task deliberately declined.
The residual risk is **accepted**, mitigated by documentation on the path
`CLAUDE.md` already routes TUI authors through. No `### Planned mitigations`
subsection is written, so Step 8d creates nothing.

## Step 9 (Post-Implementation)

Standard cleanup, archival, and merge per `task-workflow` Step 9. No worktree was
created (profile `fast`, `create_worktree: false`) — work is on the current
branch, so the merge sub-step is a no-op and archival runs via
`./.aitask-scripts/aitask_archive.sh 1251`.
