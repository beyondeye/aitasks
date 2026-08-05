---
Task: t1293_concern_block_parse_diagnostics.md
Worktree: (current branch — profile 'fast')
Branch: main
Base branch: main
Output branch: main
---

# t1293 — Concern-block parse diagnostics

## Context

t1274 made concern-block parse losses **visible**: `concern_parser.unrecovered_markers()`
returns the marker-looking lines that yielded no concern, `ConcernPickerModal`
shows `⚠ N line(s) in this block could not be parsed`, and a block that parses to
nothing warns instead of claiming "no concerns". It stopped there deliberately —
its own goal-achievement risk bullet named the two residuals and pointed them at
this task:

1. The user can see **that** lines were lost but never **what** was lost. The
   offending strings are discarded at the call site (`len(...)` is all that
   crosses into the modal), so an over-bound split marker and a producer typo are
   indistinguishable and neither can be reported as a real bug.
2. The rendered-viewport layout is verified only at 40 columns — the measured
   minimonitor companion width. Nothing pins behaviour below it.

Both were measured against the real modal before planning (see below), so this
plan fixes reproduced defects rather than hypothesised ones.

### Measured sub-40 behaviour (current code, real modal, composited screen)

| width | result |
|---|---|
| 40 | clean; region ellipsized, body visible |
| 30 | `min-width: 30` = whole screen; **OK/Cancel labels pushed off-screen** — `max-height: 80%` (24 rows) minus a help line that wraps to 5 rows at this width |
| 24 | `min-width: 30` > screen: dialog **overflows and is clipped** — no right border, text cut mid-word (`… select to sele`, `HIGH authoring-co`, `[Spac`) |

Patching the dialog to `width:100%; min-width:0; padding:0 1; max-height:100%`
plus a compact help line restores a fully-bordered, unclipped render at **both**
30 and 24, with region *and* body still on screen. That measurement is the basis
for Part 2.

---

## Part 1 — See what was lost

### Pre-phase (risk mitigations)

1. `[enumerate_picker_construction_sites]` Before touching
   `ConcernPickerModal.__init__`, run
   `grep -rn 'ConcernPickerModal(\|_unrecovered\|unrecovered=' .aitask-scripts/monitor tests`
   and write the resulting inventory into this plan as a checklist (expected
   today: `minimonitor_app.py:1727`, `monitor_app.py:2910`,
   `tests/test_concern_picker_modal.py:66` + `:338-354`,
   `tests/test_monitor_concern_action.py:351-364`, and the banner/compose reads
   in `monitor_shared.py:1422,1464`). Tick every entry as it is migrated to the
   `Sequence[str]` form; the phase is complete only when the grep re-run shows no
   site still passing or comparing an `int`.

### 1.1 `.aitask-scripts/monitor/concern_parser.py` — expose the raw block region

Add one public function beside the existing entry points (after
`unrecovered_markers`, ~`:431`):

```python
def block_region(capture_text: str) -> str | None:
    """The newest block's raw region text, or ``None`` when no fence is present.

    Same forgiving scope as :func:`parse_concerns` / :func:`unrecovered_markers`
    (``require_close=False``), so the three always describe the *same* block.

    **Display-only.** The text is returned verbatim for a human to read; it is
    never parsed into forwardable items. A shadow doc read into the pane can
    carry literal ``- [priority | region]`` example lines (the t1123 hazard),
    which is exactly why the block a user is *inspecting* and the block the
    picker *forwards* stay separate code paths.
    """
    return _last_block_region(capture_text, require_close=False)
```

Reuses the canonical private helper — no parallel region-scanning logic.

### 1.2 `.aitask-scripts/monitor/monitor_shared.py` — carry the lines, not a count

`ConcernPickerModal.__init__` (`:1415`) currently takes `unrecovered: int = 0`.
Replace it with the lines themselves and add the raw region:

```python
def __init__(
    self, concerns: list["Concern"], narrow: bool = False,
    stale: bool = False, unrecovered: Sequence[str] = (),
    raw_block: str = "",
) -> None:
    ...
    self._unrecovered = list(unrecovered)
    self._raw_block = raw_block
```

A count derived from the list (`len(self._unrecovered)`) cannot disagree with
what the inspect view shows; a separate `int` parameter alongside a list
parameter could. The banner (`:1464-1469`) keeps its wording and gains the key:

```
⚠ {n} line(s) in this block could not be parsed — [u] inspect
```

Both call sites change from `unrecovered=len(unrecovered_markers(text))` to
`unrecovered=unrecovered_markers(text), raw_block=block_region(text) or ""`:
`minimonitor_app.py:1732` and `monitor_app.py:2914`.

### 1.3 `monitor_shared.py` — new `ConcernBlockInspectModal`

Modelled on `TaskDetailDialog` (`:587-668`) — the local template for a
read-only, scrollable, `q`/`Esc`-dismissed viewer with a docked footer.

```python
class ConcernBlockInspectModal(ModalScreen):
    """Raw view of a concern block that did not fully parse (t1293)."""

    BINDINGS = [
        Binding("escape", "dismiss_dialog", "Close", show=False),
        Binding("q", "dismiss_dialog", "Close", show=False),
    ]
```

`__init__(self, unrecovered: Sequence[str], raw_block: str)`. `compose()` yields,
inside `#concern-inspect-dialog` (`width: 90%; height: 85%; border: thick $accent`):

- a header `Unparsed concern lines (N)`;
- one `Static` per unrecovered line, listed first — this is the answer to "what
  was lost";
- a `VerticalScroll` (`height: 1fr`) holding the raw block region, or
  `*(block region unavailable)*` when `raw_block` is empty;
- a docked footer `q/Esc: close`.

**Every rendering of captured text uses `markup=False`.** A concern marker is
literally `- [high | region]`; rendered as markup Rich would eat the bracket —
i.e. the inspect view would corrupt the very text the user opened it to read.
(`_ConcernRow` solves the same problem with `escape()`; `markup=False` is the
stronger choice for a verbatim dump.)

### 1.4 `monitor_shared.py` — reach it from the picker

Add to `ConcernPickerModal.BINDINGS`:

```python
Binding("u", "inspect_unrecovered", "Unparsed", show=False),
```

`u` is free: the modal binds only `escape`/`enter`/`a`/`A`, and
`_ConcernRow.on_key` (`:1327`) stops only `space`/`up`/`down`, so `u` bubbles.
(`i` is deliberately avoided — the two apps bind it to Task Info.)

```python
def action_inspect_unrecovered(self) -> None:
    if not self._unrecovered:
        self.app.notify("Nothing unparsed in this block")
        return
    self.app.push_screen(
        ConcernBlockInspectModal(self._unrecovered, self._raw_block)
    )
```

This is the first modal-pushes-modal in the `monitor/` package; the repo
precedent is `brainstorm/modals.py:622` (`self.app.push_screen` from inside a
modal). Note it in the class docstring. The picker is not dismissed — the
inspect view is pushed **over** it, so closing returns to the still-intact
selection.

Add `[u] unparsed` to `#concern-help` (full variant only; the compact variant of
Part 2 carries `u`).

### 1.5 The no-rows case (currently only a toast)

`minimonitor_app.py:1714-1723` and `monitor_app.py:2881-2896` both `return` after
a warning when a block parses to nothing. Keep the warning (it is the passive
signal, and the auto-offer path at `minimonitor_app.py:1800` /
the monitor's tick keep using it unchanged) and **additionally push the inspect
modal** — the user pressed `c` deliberately and there is nothing else to show
them:

```python
lost = unrecovered_markers(text)
if lost:
    self.notify(unparsed_concerns_msg(len(lost)), severity="warning")
    self.push_screen(
        ConcernBlockInspectModal(lost, block_region(text) or ""),
        callback=self._on_inspect_closed,      # monitor only — see below
    )
else:
    self.notify("No concerns detected on the shadow pane")
return
```

**Monitor-specific care** (`monitor_app.py`): that method holds
`self._concern_pick_busy` and releases it in a `finally` unless
`modal_owns_guard` is set. Pushing here must set `modal_owns_guard = True` and
release via a new `_on_inspect_closed(self, _result) -> None` callback (mirroring
`_on_concerns_picked`, `:2923`), otherwise a second `c` stacks inspect modals.
The existing badge-clearing (`concern_block_signature` → `_mark_concern_sig`,
`:2891-2895`) stays exactly where it is — the outcome is still definitive.

Minimonitor has no such guard, so it pushes without a callback.

---

## Part 2 — A measured width tier down to 24 columns

### 2.1 `monitor_shared.py` — the tier

```python
#: Below this many columns the picker dialog drops its fixed chrome. At 30 the
#: `.narrow` `min-width: 30` exactly fills the screen; below it the dialog
#: overflows and the composited rows are clipped mid-word with no right border.
#: 24 is the tested floor — the same width as `concern_parser._SENTINEL_SAFE_COLS`,
#: below which the block's own fences wrap and there is nothing to parse anyway.
_PICKER_XNARROW_COLS = 30
_PICKER_MIN_COLS = 24
```

CSS added to `ConcernPickerModal.DEFAULT_CSS`:

```css
ConcernPickerModal.xnarrow #concern-dialog {
    width: 100%;
    min-width: 0;
    max-height: 100%;
    padding: 0 1;
}
/* Two buttons do not fit side by side under ~34 columns — one label is clipped
   to "Can". Stack them instead of half-showing them. */
ConcernPickerModal.xnarrow #concern-buttons { layout: vertical; height: auto; }
ConcernPickerModal.xnarrow #concern-buttons Button { width: 100%; margin: 0; }
```

`border: thick` is deliberately **kept** — the intact border is what the tests
assert against to prove nothing is clipped.

The tier is applied from measured width, not from the caller's `narrow` hint, so
a full monitor in a 24-column terminal gets it too:

```python
def on_mount(self) -> None:
    self._apply_width_tier()
    ...existing first-row focus...

def on_resize(self) -> None:
    self._apply_width_tier()

def _apply_width_tier(self) -> None:
    xnarrow = self.size.width < _PICKER_XNARROW_COLS
    self.set_class(xnarrow, "xnarrow")
    self.query_one("#concern-help", Static).update(
        _CONCERN_HELP_COMPACT if xnarrow else _CONCERN_HELP_FULL
    )
```

with the two help strings hoisted to module constants:

```python
_CONCERN_HELP_FULL = (
    "[dim]\\[↑/↓] navigate  \\[Space] toggle  \\[a] all actionable  "
    "\\[A] copy all  \\[u] unparsed  \\[Enter/OK] confirm  \\[Esc] cancel[/]"
)
_CONCERN_HELP_COMPACT = "[dim]↑↓ move · spc pick · a all · A copy · u raw · ↵ ok · esc[/]"
```

`narrow` keeps its existing meaning (two-line `_ConcernRow`) and is untouched —
changing it would invalidate t1274's negative control, which relies on
`narrow=False` losing content at 40 columns.

`_ConcernRow.render()` already derives its region budget from live
`self.size.width` (`:1323`), so rows adapt to the tier with no change.

**Named fallback, if measurement at implementation contradicts the plan:** if
stacking the buttons costs enough rows to push the concern list out at a short
pane height (~20 rows), hide `#concern-buttons` at the `xnarrow` tier instead —
`Enter`/`Esc` are bound and both appear in the compact help. This will be
decided by the (24, 20) test below, and whichever way it goes is recorded in the
Final Implementation Notes.

### 2.2 `tests/test_concern_picker_modal.py` — widths 40 / 30 / 24

Generalise `_render_at_40(region, narrow)` (`:379-388`) into
`_render_at(width, region, narrow)` keeping the two `await pilot.pause()` calls,
and add a `_screen_rows(app)` helper beside `_screen_text` returning the strip
texts as a **list** (the existing `_screen_text` stays — it is what the
substring assertions use).

New assertions, one `subTest` per width in `(40, 30, 24)`:

1. **Content survives** — `assertIn("authoring-conv", screen)` and
   `assertIn("BODYMARKER", screen)`, i.e. exactly the t1274 invariant, now at
   every supported width.
2. **Nothing is clipped** — for every row that starts with the border glyph
   `█`, that row's column `width - 1` is also `█`. Under the current
   `min-width: 30` this fails at 24 (the row ends in content), which is the
   defect being fixed.
3. **Both buttons are reachable** — `"OK"` and `"Cancel"` both appear in the
   composited screen at 30 and 24 (they do not today at either width).

Negative controls, **one mutation each** (`unittest.mock.patch` on the module
constant, no source edits):

- `_PICKER_XNARROW_COLS` patched to `0` (tier never applies) → at 24 the
  no-clipping assertion **fails** and at 30 the buttons are absent. This proves
  assertions 2 and 3 discriminate, and it is the in-test reproduction of the
  measured defect.
- t1274's `test_single_line_layout_is_what_lost_them` is kept verbatim at 40 as
  the control for assertion 1. It must stay pinned at 40 — at a wide enough size
  the single-line layout fits and its `assertNotIn`s would fail.
- A short-pane case at `(24, 20)` asserting the concern row and the help line are
  both still on screen — this is what decides the stacked-vs-hidden button
  fallback in 2.1.

Existing `_Host` (`:42-71`) changes `unrecovered=0` → `unrecovered=()` and gains
`raw_block=""`; `test_unrecovered_banner_shown_only_when_lines_were_lost`
(`:338`) passes two fake lines instead of `2` and still asserts `"2 line(s)"`.

### 2.3 New picker tests for Part 1

In `tests/test_concern_picker_modal.py`:

- `u` with unrecovered lines pushes `ConcernBlockInspectModal`; the offending
  lines and a substring of the raw block are both on the composited screen.
- **Markup control**: an unrecovered line containing `- [high | x.py:1]` renders
  with its brackets intact (this fails if `markup=False`/`escape` is dropped).
- `u` with no unrecovered lines pushes nothing (negative control for the guard).
- Closing the inspect modal returns to the picker with the previous selection
  intact.

---

## Part 3 — Caller and parser tests

- `tests/test_concern_parser.py` — a `TestBlockRegion` class: returns the region
  verbatim for a complete block, for a still-streaming block (no closing fence),
  and the **newest** block only when two are present (last-block-wins, matching
  `parse_concerns`); `None` when there is no opening fence. Include an
  unrecovered marker line in the fixture and assert it is present in the returned
  region — that is the property the inspect view depends on.
- `tests/test_minimonitor_concern_action.py` — extend the existing
  `_MALFORMED_ONLY_BLOCK` fixture tests: pressing `c` still warns **and** now
  pushes `ConcernBlockInspectModal`. Negative control: a pane with no block
  pushes nothing (the existing "never warns" control extends to the modal).
- `tests/test_monitor_concern_action.py` — `test_unrecovered_count_forwarded_to_the_modal`
  (`:351-364`) asserts `screen._unrecovered == 1`; update to the list form. Add:
  the monitor's all-malformed path pushes the inspect modal, still clears the
  concern badge (`_mark_concern_sig`), and releases `_concern_pick_busy` when the
  inspect modal is dismissed (guard-leak regression — assert a second `c` is not
  swallowed).

## Part 4 — Documentation

Current-state prose only, and deliberately **no skill files**: `block_region` is
a consumer-side display helper and `u` is a TUI affordance, so neither belongs in
the shadow producer's `concern-format.md` strictness table. No `.md.j2` /
stub-surface change ⇒ no rerender, no goldens.

- `aidocs/framework/shadow_agent.md` — one line: the picker's `u` opens a raw
  view of the block when lines could not be parsed, and the all-malformed case
  opens it directly.
- `website/content/docs/tuis/minimonitor/how-to.md` — extend the concern-picker
  paragraph (`:155`) with the `u` affordance and the all-malformed behaviour; add
  `u` to the key table around `:262` if the picker's own keys are listed there,
  and state the 24-column supported floor.

### Post-phase (risk mitigations)

1. `[pin_tier_independent_of_narrow]` Add
   `test_width_tier_is_measured_not_inherited_from_narrow` to
   `tests/test_concern_picker_modal.py`: at `size=(24, 30)` with `narrow=False`
   the modal still carries the `xnarrow` class and renders unclipped, and at
   `size=(80, 24)` with `narrow=True` it does **not** carry it. Pair it with a
   negative control that patches `_apply_width_tier` to key off `self._narrow`
   instead of `self.size.width` and shows both assertions fail. Then state the
   split explicitly in `ConcernPickerModal`'s class docstring: `narrow` is the
   caller's hint and owns only the two-line `_ConcernRow` layout; the `xnarrow`
   class is derived from measured width and owns only the dialog chrome. Neither
   is derived from the other.

---

## Verification

```bash
python3 -m pytest tests/test_concern_parser.py tests/test_concern_picker_modal.py \
  tests/test_minimonitor_concern_action.py tests/test_monitor_concern_action.py \
  tests/test_concern_body_display_contract.py tests/test_minimonitor_concern_smoke.py -v
bash tests/run_all_python_tests.sh
```

`test_concern_body_display_contract.py` is in the list because it AST-scans the
whole `monitor/` package for `Concern.body` reads — a new modal that renders
concern text would surface there as an `UNCLASSIFIED` key. (The inspect modal
renders *raw capture lines*, not `Concern` objects, so it should stay invisible
to that guard; running it is how that is confirmed rather than assumed.) Its
docstring also cross-references
`ConcernPickerNarrowLayoutTests::test_display_body_hides_the_trailer_from_the_row`
by name — that method must keep its name through the width refactor.

**Every new guard must be proven to fail when its fix is removed** (patched
constant / suppressed tier / dropped `markup=False`), and the count of failures
recorded, per this repo's negative-control convention.

**Live check** (not coverable by tests): resize a minimonitor companion pane to
~24 columns with a shadow that emitted a malformed marker; press `c`; confirm
the inspect view opens directly, shows the offending line and the raw block with
brackets intact, and that closing it returns to the pane cleanly. Then with a
partially-parseable block, confirm the banner names `[u]`, that `u` opens the
same view over the picker, and that the selection survives closing it.

## Risk

### Code-health risk: low
- `ConcernPickerModal.__init__` changes an existing parameter's type
  (`unrecovered: int` → `Sequence[str]`) rather than adding a second one. Both
  production call sites and three test files must move together; a missed one
  passes an `int` and `list(2)` raises at push time · severity: low (residual —
  addressed by inline pre-phase enumerate_picker_construction_sites) ·
  → mitigation: inline pre-phase enumerate_picker_construction_sites
- The width tier is a second, runtime-measured layout switch living beside the
  caller-supplied `narrow` flag. Two knobs that both mean "small" invite a future
  reader to conflate them · severity: low (residual — addressed by inline
  post-phase pin_tier_independent_of_narrow) ·
  → mitigation: inline post-phase pin_tier_independent_of_narrow
- First modal-pushes-modal in the `monitor/` package; the dismiss/guard ordering
  in `monitor_app` (`_concern_pick_busy`) is easy to leak · severity: low ·
  → mitigation: none (covered in-plan by the Part 3 guard-leak regression test)

### Goal-achievement risk: low
- The sub-40 fix was measured against the real modal before planning, and the
  patched render at 24 was confirmed unclipped, so the layout half is
  demonstration rather than hope. Residual: the stacked-button row costs 6 rows
  and has not been measured against a *short* pane; the (24, 20) test and its
  named fallback are what close that · severity: low ·
  → mitigation: none (covered in-plan by the (24, 20) short-pane test)
- The inspect view shows the unrecovered lines and the raw block region, but the
  picker still never shows a concern's **full body** — the two-line row truncates
  it at every width, including 40. That is pre-existing and out of scope here,
  but it means "see what the shadow said" is only fully solved for the *lost*
  lines, not for long parsed ones · severity: low ·
  → mitigation: t1426

### Planned mitigations
- timing: pre-phase | name: enumerate_picker_construction_sites | type: chore | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: code-health — the `unrecovered: int → Sequence[str]` type change could miss a call site | desc: grep-verified inventory of every ConcernPickerModal construction and every _unrecovered read across production and tests, ticked off as each is migrated
- timing: post-phase | name: pin_tier_independent_of_narrow | type: test | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: code-health — two knobs (`narrow` vs the measured width tier) that both mean "small" | desc: test plus class-docstring contract asserting the xnarrow tier is derived from measured width and is independent of the caller's narrow row-layout flag, with a negative control
- timing: after | name: picker_full_body_view | type: enhancement | priority: medium | effort: low | inline_risk: medium | added_complexity: medium | addresses: goal-achievement — only the lost lines become readable, not long parsed bodies | desc: give the concern picker a way to read a focused concern's full body, which the two-line row truncates at every width including 40 | created: t1426

## Post-Review Changes

### Change Request 1 (2026-08-05) — the tier threshold was an undeclared magic number

- **Requested by user** (shadow concern, `[high | monitor_shared.py:1631]`,
  Disposition: blocking, Verified: CONFIRMED): the extra-narrow branch compares
  `self.size.width` against a private constant; `aidocs/framework/tui_conventions.md`
  requires terminal-width layout decisions to go through
  `terminal_tier()` / `is_narrow_terminal()` or to derive the breakpoint from
  live geometry. Route it through the supported mechanism, or make the
  component-geometry derivation explicit and test it.
- **Verified — partly valid, and the valid half was acted on.**
  - **Rejected:** routing through `tui_layout`. Those helpers bound the NARROW
    tier at **80** columns, so `is_narrow_terminal` is `True` for *every* width
    this modal distinguishes (24 / 30 / 40) and cannot express the decision;
    adopting it would strip the dialog chrome at 79 columns, where it fits
    perfectly. Rule 3 of that same document explicitly forbids reusing a tier
    constant as a component floor. This threshold is a **component minimum
    width**, which the document says stays with its widget.
  - **Accepted:** rule 4 ("prefer deriving the threshold from live geometry over
    any constant"). The `30` was measured but undeclared, and could silently
    drift from the `min-width: 30` it exists to track.
- **Changes made:**
  - `_PICKER_XNARROW_COLS` → `_PICKER_NARROW_MIN_WIDTH`, documented as *derived*:
    a dialog whose declared minimum is N cells cannot fit a screen of N or fewer,
    so N **is** the boundary. The docstring also records why `tui_layout` is the
    wrong mechanism, so the next reader does not "fix" it back.
  - New drift guard `test_tier_threshold_is_derived_from_the_declared_min_width`
    parses `min-width` out of the live `DEFAULT_CSS` and asserts equality, so
    retuning the stylesheet moves the tier with it.
  - New `test_threshold_is_a_component_floor_not_a_terminal_tier` pins that a
    79-column terminal (NARROW tier) does **not** get the stripped chrome.
  - `SUPPORTED_WIDTHS` in the layout tests now reads the production constants
    instead of hard-coding 30 / 24.
- **Discrimination proven:** two new negative controls — retuning the CSS
  `min-width` without moving the constant, and swapping the comparison for
  `is_narrow_terminal` — each fail the matching test, and pass again on restore.

## Final Implementation Notes

- **Actual work done:** as planned. `concern_parser.py`: `block_region()` plus a
  fourth row in the module strictness table. `monitor_shared.py`:
  `ConcernBlockInspectModal`, `unrecovered` carrying the **lines** rather than a
  count, `raw_block`, the `u` binding and `action_inspect_unrecovered`, the
  measured `xnarrow` chrome tier with `_apply_width_tier` on mount and resize,
  and the full/compact help constants. `minimonitor_app.py` / `monitor_app.py`:
  pass the lines and the raw region, and open the raw view directly on the
  all-malformed path (the monitor additionally gained `_on_inspect_closed` to
  release its pick guard). Docs: `aidocs/framework/shadow_agent.md` and the
  minimonitor how-to page. No skill files were touched, so no rerender/goldens.
- **Deviations from plan:**
  - **Buttons at the narrow tier: the plan's named fallback was taken.** The plan
    preferred stacking OK/Cancel; measured at 24x20 the stacked pair costs 6 rows
    and evicted the help line — the only place `u` / `a` / `A` are named. Docking
    the help instead made it collapse entirely. The buttons are hidden at the
    tier: they are fully redundant with Enter/Esc, which the compact help does
    name, and nothing is ever left half-drawn. The plan's stated trigger for the
    fallback was "the concern list is pushed out", which did **not** happen — the
    fallback was taken for the adjacent reason recorded here.
  - The tier bound is **inclusive** (`<=`). The plan assumed the defects began
    below 30; measurement showed both already bite *at* 30 (the dialog exactly
    fills the screen, and the buttons are already off-screen there).
- **Issues encountered:**
  - The banner's `[u]` was being eaten as Rich's underline tag and rendered as
    nothing — caught by rendering the real modal, not by any test. Now escaped
    (`\\[u]`) and pinned.
  - Rich markup is more destructive here than expected: the canonical marker
    `- [high | x.py:1] a good one` renders as `-  a good one`, and a bare `[/]`
    in a body raises `MarkupError` and would take the modal down. Both shapes are
    now in the inspect-view fixture, and `markup=False` covers both.
  - The compact help line **wraps**, so `u raw` is not a contiguous substring of
    the composited screen. Phrase assertions go through a `_flat_text` helper
    that strips borders and collapses whitespace; substring assertions on a
    line-oriented screen dump cannot see across a wrap.
  - The region prefix shortens with the width (24 columns leaves `authoring…`),
    so the sweep asserts the prefix that survives everywhere. Discrimination is
    unaffected — under the guarded failure the region vanishes entirely.
- **Key decisions:**
  - `unrecovered` carries the **lines**, not a count. A count derived with
    `len()` cannot disagree with what the inspect view shows; a separate `int`
    parameter beside a list parameter could.
  - `block_region` is **display-only** and documented as such. The block a user
    inspects and the block the picker forwards stay separate code paths, because
    a shadow doc read into the pane can carry literal example markers (t1123).
  - The chrome tier is keyed on **measured width**, independent of the caller's
    `narrow` row-layout hint, so a full-width monitor in a tiny terminal gets it
    too — and `narrow`'s meaning is unchanged, which keeps t1274's negative
    control valid.
  - The threshold is a **component minimum width**, not a terminal tier, and is
    derived from the dialog's own declared `min-width` (see Change Request 1).
  - The picker is pushed *under* the inspect view rather than dismissed, so the
    selection survives a look at the raw block.
- **Upstream defects identified:** None
- **Test-harness note:** every new guard was proven to fail when its fix is
  patched out of the real source — 9 controls: `markup=False` dropped, `[u]`
  unescaped, tier disabled, CSS `min-width` drift, tier routed through
  `is_narrow_terminal`, tier keyed off `narrow`, the `u` empty-list guard
  removed, the monitor's guard-release callback removed, and `block_region` made
  strict. All 9 fail under mutation and pass on restore.

## Step 9 (Post-Implementation)

Standard: merge approval into `main`, `./ait gates run 1293` (declares
`risk_evaluated`), then archival.
