---
Task: t2128_minimonitor_phase_color_and_glyph.md
Base branch: main
Output branch: main
---

# t2128 — Minimonitor: per-phase colour + leading glyph

## Context

In `ait minimonitor` each gated agent card has a detail row merging the advisory
workflow phase with gate counts (`IMPLEMENT ⏸ · 1/4 1p`). The whole row is
`[dim]`, so the phase does not stand out. Give each phase its own colour and a
leading 1-cell glyph, on both the list rows and the pinned own-agent card.
Display-only; the phase stays advisory.

**Decided with the user (planning Q&A):**

| phase      | glyph | style |
|------------|-------|-------|
| PLAN       | `◔` U+25D4 | `dim` (the current colour) |
| IMPLEMENT  | `◕` U+25D5 | `#22863a` (green) |
| POSTIMPL   | `◉` U+25C9 | `#1e90ff` (the DONE colour, without its bold) |
| UNKNOWN (all `unknown …` variants) | `◌` U+25CC | `dim` |

Glyphs are a fill-level family (fills as the task advances; dotted = cannot
tell). Measured from each font's cmap (`tests/tools/regen_font_coverage.read_cmap`):
all four are covered by **both** `SUPPORTED_FONTS`, are not in the
`_EMOJI_CAPABLE` table, and are East-Asian-Width **Neutral** (exactly 1 cell).
The trailing ` ⏸` is not emphasised separately — it takes the phase's style.

**IMPLEMENT green, chosen by WCAG contrast** against the focused-card highlight
(`MiniPaneCard:focus { background: $accent }` = `#ffa62b` orange under the default
`textual-dark` theme — minimonitor sets no theme) and against POSTIMPL's blue:

| candidate | on focus orange | on dark bg `#121212` | on light bg `#E0E0E0` | vs POSTIMPL `#1e90ff` |
|---|---|---|---|---|
| **`#22863a`** | **2.37** | **4.05** | **3.50** | **1.43** |
| `#3fb950` (bright) | 1.30 | 7.37 | 1.92 | 1.27 |
| `#16a34a` | 1.69 | 5.68 | 2.50 | 1.02 |
| `#1e90ff` (POSTIMPL itself) | 1.66 | 5.79 | 2.45 | — |

An orange highlight caps any hue's contrast (lighter greens vanish on it, darker
ones on the dark background); `#22863a` is the balance point, beats POSTIMPL's
own contrast on the highlight, and differs from the blue in **luminance** as well
as hue (survives colour-blindness). It is darker/bluer than Textual's ACTIVE
`green` (`#008000`) only slightly — the phase row sits two rows below the status
badge, and the glyph disambiguates.

## Implementation

### 1. `.aitask-scripts/monitor/monitor_shared.py` — the phase→mark table

- Split the DONE colour out so the phase can reuse it without the bold:
  `STATE_COLOUR_DONE = "#1e90ff"`; `STATE_STYLE_DONE = f"bold {STATE_COLOUR_DONE}"`
  (ratified value `"bold #1e90ff"` unchanged; keep the existing comment).
  Add `PHASE_COLOUR_IMPLEMENT = "#22863a"` with a comment recording the contrast
  rationale (focus `$accent` orange, dark/light backgrounds, POSTIMPL blue).
- Add, after the state styles (workflow_phase is already imported there):
  ```python
  # Advisory workflow-phase marks (t2128): one (glyph, style) per member of
  # workflow_phase.PHASES — keyed off that tuple, never re-listed elsewhere;
  # a drift guard pins the key set. Glyph evidence: font_coverage.json.
  PHASE_MARKS: dict[str, tuple[str, str]] = {
      "PLAN": ("◔", "dim"),
      "IMPLEMENT": ("◕", PHASE_COLOUR_IMPLEMENT),   # "#22863a", contrast note
      "POSTIMPL": ("◉", STATE_COLOUR_DONE),
      workflow_phase.UNKNOWN_PHASE: ("◌", "dim"),
  }

  def phase_mark(sig) -> tuple[str, str]:
      """(glyph, style) for a PhaseSignal; any non-member reads as UNKNOWN."""
      return PHASE_MARKS.get(getattr(sig, "phase", None),
                             PHASE_MARKS[workflow_phase.UNKNOWN_PHASE])
  ```
  Every `unknown (…)` / `unknown ⏸` / `unknown?` variant has `sig.phase ==
  UNKNOWN_PHASE`, so they all get `◌` + dim.

### 2. `.aitask-scripts/monitor/minimonitor_app.py`

a. Import `PHASE_MARKS`, `phase_mark` from `monitor.monitor_shared`.

b. Split the shed ladder so budgeting stays on plain text and styling happens after:
   - New `_gate_phase_parts(phase, gates, budget, glyph="") -> tuple[str, str]`
     returning `(head, tail)` — the budgeted phase segment (glyph included) and
     gate segment. `lead = f"{glyph} " if glyph and phase else ""`,
     `head = lead + phase`. Same rungs as today, but the glyph's cells are counted
     everywhere: rung 1 measures `f"{head} · {candidate}"`; rung 2
     `room = budget - cell_len(f" · {short}") - cell_len(lead)` and, if
     `room >= _MIN_PHASE_CELLS`, returns `(lead + _clip(phase, room), short)` —
     the glyph survives, only the phase text is clipped; rung 3 drops head
     (glyph with it); rung 4 terminal clip. The phase-only path goes through one
     shared helper `_phase_head(phase, budget, glyph)`: full `head` if it fits;
     with no glyph, `_clip(phase, budget)` (today's behaviour, so existing tests
     hold); with a glyph, `lead + _clip(phase, budget - cell_len(lead))` while that
     leaves `>= _MIN_PHASE_CELLS`, else the **glyph alone** (1 cell, still carries
     the phase's shape + colour), else `""`. Rung 2 uses the same room rule, so
     list rows and the pinned card shed identically.
   - `format_gate_phase_row(phase, gates, budget, glyph="")` becomes
     `" · ".join(p for p in _gate_phase_parts(...) if p)` — the existing plain
     API and every existing ladder test keep working.
   - New `format_gate_phase_markup(sig, gates, budget) -> str`: glyph/style from
     `phase_mark(sig)`, phase from `workflow_phase.render_phase_narrow(sig)`,
     parts from `_gate_phase_parts`; returns
     `[<style>]<markup_literal(head)>[/]` + `[dim] · <markup_literal(tail)>[/]`
     (separator only when both exist; either may be absent; `""` when both are).
   - New `format_phase_markup(sig, budget) -> str` for the pinned card: `""` when
     the narrow phase is empty, else `[<style>]<markup_literal(_phase_head(phase,
     budget, glyph))>[/]` — budgeted, glyph and style preserved where feasible.
   - Fix the stale docstring arithmetic ("36-cell budget" → the 34-cell detail
     budget; worst case `◌ unknown (rec off) · 0/4 1p 1f 1s` = 34 cells, exactly
     fits) and note the glyph in the budget block's `gates` line.

c. `_agent_card_text`: replace the `format_gate_phase_row(...)` +
   `f"\n  [dim]{merged}[/]"` with
   `merged = format_gate_phase_markup(self._phase_for_snap(snap, info), summary, budget)`
   and `line1 += f"\n  [/dim]{merged}"`. The `[/dim]` closes the span
   `_title_row` deliberately leaves open (t2017) — without it the phase colour
   paints dimmed (probed: `[dim]t\n  [#ff8800]P[/]` gives P both styles). Safe
   against a title ending in `\`: the backslash is followed by the newline, not
   the tag (probed). `_title_row` is always emitted immediately before this row
   in the same `if info:` block; update its comment to say the gate/phase row
   closes the span.

d. Pinned card — **its phase row is now budgeted** (it was not, and did not need
   to be: `unknown (rec off)?` is 18 cells and fits the 18-cell row at width 22
   exactly; the glyph's 2 cells make it wrap, and `_OWN_PANEL_MAX_ROWS` reserves
   one phase row, so the continuation would be hidden by the 7-row cap —
   `◌ unknown (rec` — verified from the CSS: `#mini-own-agent` padding 0,
   `.mini-own-card` padding 0 1, phase indent 2).
   New `_own_phase_budget(target_width) = max(0, target_width - _ROW_PADDING -
   _DETAIL_INDENT)` (no scrollbar term: the panel is `overflow-y: hidden`;
   clamped only at zero, same reasoning as `_detail_budget`), documented in the
   budget block. `_own_phase_text` returns
   `format_phase_markup(sig, _own_phase_budget(self._target_width))`;
   `_own_card_text` appends `Content.from_markup(f"\n  {phase}")` and its
   docstring says `phase` is framework-built markup (text already made literal).
   The `_own_phase_state` change-compare still works (compares rendered markup).
   Frozen / parked rows keep rendering no phase (untouched paths).

### 3. Glyph evidence (the repo's codepoint policy, t1638/t1685)

- `tests/tools/regen_font_coverage.py`: add `0x25D4, 0x25D5, 0x25C9, 0x25CC` to
  `EXTRA_MEASURED_CODEPOINTS` with a "CHOSEN (t2128)" comment line each;
  regenerate `tests/data/font_coverage.json` (fonts are installed locally).
- `tests/test_mark_glyphs_single_source.py`: add
  `test_the_phase_glyphs_evidence_is_recorded` next to the frozen-marker test:
  for every glyph in `PHASE_MARKS`, one codepoint, covered `true` by every
  manifest font, not in `_EMOJI_CAPABLE`, EAW not `W`/`F`; and assert the
  generator measures each codepoint.

### 4. Tests

- `tests/test_minimonitor_gate_phase_row.py`
  - Card/composited expectations gain the glyph (`◕ IMPLEMENT ⏸ · 3/4 pass,
    1 pending`, `◔ PLAN`, `◉ POSTIMPL · 1/4 1p 1f 1s`,
    `◌ unknown (rec off) · 0/4 1p 1f 1s`); the 3-row / no-ellipsis / ≤ budget
    assertions stay.
  - New ladder tests with a glyph: best case joins verbatim; rung 2 keeps the
    glyph and clips the phase; rung 3 drops glyph+phase; a sweep over budgets
    0..40 × every phase variant (`render_phase_narrow` of all PHASES, each
    `_UNKNOWN_TEXT` cause, both resolution suffixes) asserting
    `cell_len(row) <= budget` — the glyph is counted before shedding.
  - New `PhaseMarkTests`: ratified values pinned (the table above); drift guard `set(PHASE_MARKS) == set(PHASES)`; every
    UNKNOWN variant maps to the unknown mark; each style parses with Textual's
    `parse_style`; `format_phase_markup` renders glyph + text in its style.
  - Styled-segment test on `_agent_card_text` row 3 via `Content.from_markup`:
    phase cells carry exactly the phase style (e.g. `{"#22863a"}`, **no `dim`**),
    gate cells carry `{"dim"}`.
- `tests/test_minimonitor_top_chrome_render.py` (`OwnPanelSizingTests`) — the
  composited regression for the pinned path: `_populate`/`_run` gain an optional
  `phase_sig` that stubs `_phase_for_snap` (not `_own_phase_text`), so the real
  budgeted `_own_phase_text` runs. For widths 40/30/26/22 ×
  `OWN_WINDOW_PATHOLOGICAL` (2 name rows) × full title (2 rows) × the longest
  variants — `unknown (rec off)?` (recording off + unresolved), `unknown ⏸?`,
  `unknown (ledger)`, `IMPLEMENT ⏸?`, `POSTIMPL ⏸~` — assert: the expected
  budgeted phase plain text appears **whole on one composited row** inside the
  panel band, starts with its glyph, is `<= width - 4` cells, and the panel stays
  `<= _OWN_PANEL_MAX_ROWS` with no scrollbar. Unbudgeted, width 22 fails this
  (the row would read `◌ unknown (rec`). Plus a pure test of `format_phase_markup`
  across budgets 0..40: plain ≤ budget, glyph kept down to budget 1, style kept.
- `tests/test_markup_colour_contract.py`: a composited test (`_CompositedCase`
  pattern) that the card's IMPLEMENT glyph paints the same as a live
  `[#22863a]` reference — the check a span assertion cannot make if the open
  title `[dim]` leaked. POSTIMPL likewise against `STATE_COLOUR_DONE`.
- `tests/test_monitor_markup_literal_sinks.py`: `_own_card_text`'s `phase` is now
  markup, so the `title_and_phase` case input and the hostile own-panel test pass
  `"[dim]planning[/]"` — the frozen `OWN_PANEL_BEFORE` pins stay byte-identical.
  Add one case that a `format_phase_markup` phase renders its glyph in its style.
- Run the existing neighbours unchanged: `test_monitor_frozen_filter.py`,
  `test_minimonitor_top_chrome_render.py`, `test_minimonitor_own_mark.py`,
  `test_workflow_phase.py` (`render_phase*` untouched), `test_textual_markup_colours.py`
  (Rule C on the new `[/dim]` row), `test_minimonitor_row_budget.py`.

### 5. Docs

- `website/content/docs/tuis/minimonitor/how-to.md`: the third-line bullet and
  example become `◕ IMPLEMENT ⏸ · 1/4 1p 1f` with "the phase is coloured and
  led by a symbol, the gate counts stay dimmed"; the phase table gains a
  Symbol/Colour column; shed paragraph: "the phase is clipped (its symbol
  stays), then dropped together with its symbol"; pinned-card paragraph: same
  symbol and colour as the list rows.
- `website/content/docs/tuis/minimonitor/_index.md`: comparison-table example
  `◕ IMPLEMENT ⏸ · 1/4 1p`.
- `cd website && python3 check_links.py --build`.

### Out of scope (to offer as a follow-up at the end)

- `⏸` U+23F8 itself is emoji-capable and covered by neither supported font
  (t1685's recorded rejection) yet ships in the phase text — a separate glyph fix.
- `ait monitor`'s labelled `render_phase` row is unchanged.

## Verification

```bash
for t in test_minimonitor_gate_phase_row test_mark_glyphs_single_source \
         test_markup_colour_contract test_monitor_markup_literal_sinks \
         test_textual_markup_colours test_monitor_frozen_filter \
         test_minimonitor_top_chrome_render test_minimonitor_own_mark \
         test_workflow_phase test_minimonitor_row_budget; do
  ~/.aitask/venv/bin/python tests/$t.py || echo "FAIL $t"; done
~/.aitask/venv/bin/python tests/tools/regen_font_coverage.py --check
bash tests/run_all_python_tests.sh   # read only the last verdict line
```

Step 9 (Post-Implementation): commit code (`enhancement: … (t2128)`), plan via
`aitask_task_commit.sh`, archive per the workflow.

## Risk

### Code-health risk: low
- The new gate/phase row closes the title row's deliberately open `[dim]` with a named `[/dim]`; if a future change emitted this row without the title row before it, Textual raises `MarkupError` on render · severity: low · → mitigation: none (covered by plan step 2c — the two are emitted in one `if info:` block, the comment is updated, and the card/composited tests exercise the path)
- `_own_card_text`'s `phase` parameter changes from plain text to framework markup; a caller passing user text would become a markup sink · severity: low · → mitigation: none (covered by step 2d/4 — the only producer is `format_phase_markup`, which applies `markup_literal`; the sinks test is updated)

- The glyph widens the pinned card's phase row, which was never budgeted; at narrow widths it would wrap and the continuation be hidden by `_OWN_PANEL_MAX_ROWS` (raised in plan review, reproduced at width 22) · severity: medium (residual low) · → mitigation: none (covered in-plan by step 2d's `_own_phase_budget` + shared `_phase_head` ladder and step 4's composited own-panel regression)

### Goal-achievement risk: low
- A span-level test can pass while the phase still paints dimmed (the open title span) — the exact "phase does not stand out" problem · severity: low · → mitigation: none (covered by step 4's composited painting test)
