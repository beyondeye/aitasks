---
Task: t1479_merge_minimonitor_gates_and_phase_into_one_row.md
Base branch: main
Output branch: main
plan_verified: []
---

# t1479 — Merge the minimonitor gates + phase lines into one row

## Context

In `ait minimonitor`, an agent whose task has a gate ledger renders a **four-line**
card:

```
 ★ ● ◆ ≈ agent-pick-1420      PROMPT 12s
   merge the gates and phase lines
   gates: 3/4 pass, 1 pending
   phase: IMPLEMENT ⏸
```

Both trailing lines come from `_agent_card_text`
(`.aitask-scripts/monitor/minimonitor_app.py:836-842`) and convey one thing between
them — how far along the task's gate workflow is — while costing two of four rows in
a narrow, tall side column. `ait monitor` already merges them onto one line
(`monitor_app.py:1579-1595`); its comment blames minimonitor's row width, but that
was never measured against appending the phase to the *gates* line instead of to the
status row.

Outcome: a gated task's minimonitor card becomes **3 rows**, with the gate summary
and the advisory phase on one line that fits the pane's cell budget, and a stated
shed order for the cases that still would not.

## Decisions (t1479's "decisions to make")

1. **Merged format** — `<PHASE><⏸> · <gate summary>`, phase first, **labels dropped**
   (`IMPLEMENT ⏸ · 3/4 pass, 1 pending` = 33 cells). Dropping `gates: ` / `phase: `
   buys ~13 cells; both halves are self-describing in context. The naive labelled
   join is rejected — it fits only the single best case and `Static` *wraps* rather
   than clips, so every other case would re-wrap to two rows and save nothing.
2. **Shed order when over budget — the gate counts are the last thing to give way.**
   Ladder, in order: (a) abbreviate the gate tail — drop the word `pass`, render
   detail counts as `<n><letter>` (`p`/`f`/`s`), so
   `1/4 pass, 1 pending, 1 failed, 1 stale` → `1/4 1p 1f 1s`; (b) **clip the phase**,
   not the gates — the phase is the coarser, re-derivable signal, while a failed or
   stale count is exactly what must stay visible; (c) if the clipped phase would fall
   below 4 cells (no information left), drop the phase entirely and give the whole
   budget to the gates; (d) terminal backstop, only reachable if the abbreviated gate
   summary *alone* exceeds the budget: clip it with a cell-aware ellipsis, so the row
   can never wrap. (b)–(d) are unreachable at realistic widths (worst realistic case
   is 32 of 36 cells) and exist so the failure mode is stated rather than emergent.
3. **Where phase shortening lives** — a new `render_phase_narrow()` beside the shared
   `render_phase()` in `.aitask-scripts/lib/workflow_phase.py`, both reading one
   variant table. `render_phase()`'s output is unchanged, so `ait monitor` is
   untouched (pinned by test).
4. **Docked panel** (`_own_card_text`, the followed agent) — stays **phase-only, no
   gate summary**: the narrowed static-panel contract (t944 / t1133 / t1322 / t1383 /
   t1420) is not widened. It does switch to the label-free narrow renderer so both
   surfaces in the same 40-column pane read identically. Recorded in the docstring.
5. **Full monitor** — unchanged. Decision 3 keeps the shared renderer's output
   byte-identical, so no `monitor_app.py` edit is needed.

## Column budget (the one place the arithmetic lives)

```
target_width (default 40, `mm_cfg["width"]`)
  − 2   MiniPaneCard `padding: 0 1`          ⇒ 38  usable row      = _row_budget()
  − 2   the "  " indent every detail row carries
  = 36  content budget for a detail line     = _detail_budget()   (target_width − 4)
```

`target_width − 4` is the same expression `_own_agent_identity_text` already uses for
its wrap width (`minimonitor_app.py:915`). Measured with `rich.cells.cell_len`
(`⏸`, `·`, `…` are 1 cell each):

| line | cells | verdict |
|---|---|---|
| `IMPLEMENT ⏸ · 2/2 pass` | 22 | fits |
| `IMPLEMENT ⏸ · 3/4 pass, 1 pending` | 33 | fits |
| `POSTIMPL · 1/3 pass, 1 pending, 1 failed` | 40 | shed (a) → `POSTIMPL · 1/3 1p 1f` (21) |
| `POSTIMPL · 1/4 pass, 1 pending, 1 failed, 1 stale` | 49 | shed (a) → `POSTIMPL · 1/4 1p 1f 1s` (23) |
| `unknown (rec off) · 0/4 1p 1f 1s` (worst realistic, post-shed) | 32 | fits |

## Coordination with t1351 (`t1351_minimonitor_row_width_audit`, still `Ready`)

t1351 owns **row 1** of the same card (mark × shadow × compare-mode × status × name)
and the cell-width-aware replacement of the `len()`-based caps in `_agent_card_text` /
`_other_card_text`. This task owns rows 3-4. They touch the same method and the same
38-cell budget, so this plan fixes the hand-off **now** instead of leaving it to
whoever lands second:

- **Shared API, defined here.** `_ROW_PADDING`, `_DETAIL_INDENT`, `_row_budget()` and
  `_detail_budget()` land in `minimonitor_app.py` as the single arithmetic site.
  `_row_budget()` is not consumed by this task — it exists so t1351 has row 1's budget
  to *adopt* rather than restate, which is exactly its AC "the row's column budget is
  documented in one place with the arithmetic". The `_detail_budget` docstring carries
  a forward pointer naming t1351 as row 1's owner (a docstring pointer, not an edit to
  t1351's task file).
- **Compatibility requirement, both directions.** The merged line is machine-generated
  (phase vocabulary + integer counts + `⏸ · …`), never user-authored text, so the
  double-width hazard t1351 owns does not reach it; and it is already cell-aware
  (`cell_len` / `set_cell_size`), so t1351's truncation change has nothing to do here.
  Conversely, **this task's tests must not encode row-1 truncation semantics**: an
  over-budget row 1 *wraps* (t1351 captured `agent-pick-1326-lon…  PROMPT` / `123s`),
  which would break a naive "card is 3 rows" claim under either `len()` or `cell_len`
  caps. Every card-shape / composited fixture here therefore uses a short, single-cell
  window name that fits row 1 with headroom, so the assertions stay true whichever
  truncation implementation is in force.
- **No dependency edge is added.** Either order works under the contract above; t1351
  is `priority: low` and blocking this presentational change on it would buy nothing.

## Implementation

### 1. `.aitask-scripts/lib/workflow_phase.py` — add the narrow renderer

Refactor `render_phase` (line 510) so both renderers share one branch table:

```python
# Long / narrow text per UNKNOWN cause. One constant per value set: both
# renderers read this table, so a cause can never render on one surface and
# silently vanish on the other.
_UNKNOWN_TEXT: dict[str, tuple[str, str]] = {
    "recording_off": ("unknown (gate recording off)", "unknown (rec off)"),
    "ledger_only":   ("unknown (ledger only)",        "unknown (ledger)"),
    "waiting":       ("unknown ⏸",                    "unknown ⏸"),
}


def _phase_body(sig: PhaseSignal, *, narrow: bool) -> str:
    """Label-free phase text shared by both renderers; ``""`` when there is
    nothing honest to say."""
    if sig.phase == UNKNOWN_PHASE:
        if sig.recording == "off":
            cause = "recording_off"
        elif "no prompt markers" in sig.detail:
            cause = "ledger_only"
        elif sig.waiting == "WAITING":
            cause = "waiting"
        else:
            return ""
        return _UNKNOWN_TEXT[cause][1 if narrow else 0]
    glyph = " ⏸" if sig.waiting == "WAITING" else ""
    return f"{sig.phase}{glyph}"


def render_phase(sig: PhaseSignal) -> str:      # output byte-identical to today
    body = _phase_body(sig, narrow=False)
    return f"phase: {body}" if body else ""


def render_phase_narrow(sig: PhaseSignal) -> str:
    """Label-free, shortened phase for a narrow surface (minimonitor's 40-column
    rows), where it shares one line with the gate summary. Not a replacement for
    :func:`render_phase` — the labelled form stays canonical for `ait monitor`."""
    return _phase_body(sig, narrow=True)
```

### 2. `.aitask-scripts/lib/gate_ledger.py` — abbreviated gate summary

Beside `compact_gate_summary` (line ~367), single-source the tail labels and add the
narrow shed:

```python
# (label, abbreviation) for compact_gate_summary's tail parts, in render order.
GATE_SUMMARY_TAIL = (("pending", "p"), ("failed", "f"), ("stale", "s"))
```

`compact_gate_summary` builds its tail from that table (same output as today):

```python
    counts = {"pending": n_pending, "failed": n_fail, "stale": n_stale}
    parts = [f"{n_pass}/{total} pass"]
    parts += [f"{counts[k]} {k}" for k, _ in GATE_SUMMARY_TAIL if counts[k]]
    return ", ".join(parts)
```

```python
def abbreviate_gate_summary(summary: str) -> str:
    """Narrow-surface shed of :func:`compact_gate_summary`:
    ``"1/4 pass, 1 pending, 1 failed"`` → ``"1/4 1p 1f"``. Reads the same
    :data:`GATE_SUMMARY_TAIL` table the long form writes, so the two cannot
    drift; an unrecognised part is left verbatim rather than dropped — a narrow
    row may be terse, never untrue."""
```

### 3. `.aitask-scripts/monitor/minimonitor_app.py` — the merged row

Add `import gate_ledger` (the `lib/` path is already on `sys.path`; `monitor_core.py:55`
imports it the same way) and `from rich.cells import cell_len, set_cell_size`.

Module scope, carrying the budget arithmetic and the t1351 hand-off note:

```python
_ROW_PADDING = 2      # MiniPaneCard `padding: 0 1`
_DETAIL_INDENT = 2    # the "  " every detail row under the name line carries
_MIN_PHASE_CELLS = 4  # below this a clipped phase carries no information


def _row_budget(target_width: int) -> int: ...      # target_width - 2  (row 1; t1351)
def _detail_budget(target_width: int) -> int: ...   # target_width - 4  (rows 2-3)


def _clip(text: str, budget: int) -> str:
    """Cell-aware terminator: `Static` wraps rather than clips, so anything that
    could exceed its budget must be cut here or it costs a whole extra row.

    The return is ALWAYS ≤ ``budget`` cells, degenerate budgets included — the
    ellipsis itself costs a cell, so budgets 0 and 1 are handled before it is
    appended rather than overshooting by one."""
    if budget <= 0:
        return ""
    if cell_len(text) <= budget:
        return text
    if budget == 1:
        return "…"
    return set_cell_size(text, budget - 1).rstrip() + "…"


def format_gate_phase_row(phase: str, gates: str, budget: int) -> str:
    """One line for the advisory phase + the gate summary (t1479).

    <budget arithmetic table, and the decision-2 shed ladder, documented here>
    """
```

Ladder, implemented exactly as decision 2 (each step tried in order, first fit wins):

```python
    if not phase and not gates:
        return ""
    if not gates:
        return _clip(phase, budget)
    short = gate_ledger.abbreviate_gate_summary(gates)
    if not phase:
        for g in (gates, short):
            if cell_len(g) <= budget:
                return g
        return _clip(short, budget)
    for g in (gates, short):                       # (a) abbreviate the tail
        line = f"{phase} · {g}"
        if cell_len(line) <= budget:
            return line
    room = budget - cell_len(f" · {short}")        # (b) the PHASE gives way
    if room >= _MIN_PHASE_CELLS:
        return f"{_clip(phase, room)} · {short}"
    if cell_len(short) <= budget:                  # (c) drop the phase entirely
        return short
    return _clip(short, budget)                    # (d) terminal backstop
```

Single exit through `_clip`, so the budget guard also covers the single-half cases —
today a lone `gates:` line can reach 38 cells and wrap.

In `_agent_card_text` (lines 836-842) replace the two blocks with:

```python
                merged = format_gate_phase_row(
                    workflow_phase.render_phase_narrow(
                        self._phase_for_snap(snap, info)),
                    self._gate_cache.summary_for(info) or "",
                    _detail_budget(self._target_width),
                )
                if merged:
                    line1 += f"\n  [dim]{merged}[/]"
```

In `_own_phase_text` (line 1012) swap `render_phase` → `render_phase_narrow`, and
record decision 4 in `_own_card_text`'s docstring (phase-only by design; no gate
summary; label-free for in-pane consistency).

### 4. `tests/test_minimonitor_gate_phase_row.py` (new) — five distinct test classes

1. **`NarrowPhaseRendererTests`** — all five `render_phase_narrow` branches, **plus a
   guard pinning `render_phase`'s four labelled outputs verbatim** (the negative
   control for decision 5: `ait monitor` renders through that function and is
   otherwise untested).
2. **`AbbreviateGateSummaryTests`** — the documented examples, `""` → `""`, an
   unrecognised part surviving verbatim, and a **drift guard**. The guard covers the
   **tail parts only**: `compact_gate_summary` always emits a leading
   `<n>/<total> pass` head whose word is deliberately *not* in `GATE_SUMMARY_TAIL`
   (the abbreviator strips it rather than mapping it), so a literal "every emitted
   label is in the table" assertion would fail on `pass`. Concretely: drive
   `compact_gate_summary` with a state producing every tail part, `split(", ")`, assert
   the head matches `^\d+/\d+ pass$` and is rendered as bare `<n>/<total>` by the
   abbreviator, then assert every **remaining** part's word has an entry in
   `GATE_SUMMARY_TAIL` and is abbreviated. The two components are modelled separately
   because they shed separately.
3. **`MergedRowLadderTests`** (pure `format_gate_phase_row`, no Textual) — best case
   verbatim; phase-only; gates-only; both empty; over-budget → abbreviated; and one
   case per shed rung: an over-long phase must come back **clipped with the
   `1p 1f 1s` tail intact** (rung b), a phase squeezed under `_MIN_PHASE_CELLS` must
   be dropped rather than stubbed (rung c), and an absurd gate summary must hit the
   terminal clip (rung d), plus the degenerate budgets 0 and 1 (`""` and `"…"`, never
   two cells). Every case asserts `cell_len(...) <= budget` — **in cells, never
   `len()`**.
4. **`CardShapeTests`** (markup level, no mounting) — call `_agent_card_text` on a
   `__new__`-constructed app stubbed per `tests/test_minimonitor_other_section.py`'s
   `_mk_list_app`, extended so the gated branch actually runs: `_task_cache` returns a
   real `TaskInfo`, `_gate_cache` stubs both `summary_for` **and** `phase_for`, the
   snapshot carries `content` / `awaiting_input` / `awaiting_input_kind`, and
   `_target_width = 40`. Assert the returned markup has exactly **two** newlines
   (name → title → merged = 3 rows, down from 4), that the third line carries both
   halves joined by `·`, and that neither `gates: ` nor `phase: ` appears. Window name
   short and single-cell (t1351 hand-off). This is a *different* test from 5: it pins
   the card's line structure at the source, where a wrap cannot mask a missing line.
5. **`CompositedRowTests`** — the AC's composited-screen assertion at width 40, reusing
   the `_RowHost` pattern from `tests/test_minimonitor_other_section.py:258-312` (mount
   a real `MiniPaneCard` in a `#mini-pane-list` `VerticalScroll`, read
   `app.screen._compositor.render_strips()`). Three cases: best case, the multi-part
   gate summary, and the longest `unknown (…)` phase variant. For each: the merged row
   is on screen, is **not ellipsised**, is ≤ 38 cells, and the card occupies exactly 3
   non-blank rows.

## Verification

1. New + neighbouring modules (venv pytest directly — a path argument *widens* the
   repo runner):
   ```bash
   ~/.aitask/venv/bin/python -m pytest -q \
     tests/test_minimonitor_gate_phase_row.py tests/test_minimonitor_other_section.py \
     tests/test_minimonitor_own_mark.py tests/test_minimonitor_own_task_info.py \
     tests/test_workflow_phase.py tests/test_monitor_gate_cache.py \
     tests/test_monitor_gate_summary.py tests/test_gate_ledger_python_parser.py
   ```
2. Full Python suite: `bash tests/run_all_python_tests.sh` — read only the last line.
3. **Live 40-column tmux capture** (AC 7, not only Textual's headless renderer): on an
   isolated socket (`tmux -L ait_t1479_$$`), a session sized `-x 40`, a window named
   `agent-pick-1479` (t1479's own ledger supplies real gate runs) plus a pane running
   `./ait minimonitor`; `capture-pane -p` and confirm the card is 3 rows with the
   merged line intact and unwrapped. Paste the capture into the Final Implementation
   Notes. Kill the server afterwards (`tmux -L … kill-server`).
4. `ait monitor` unchanged: covered by the `render_phase` pin in step 1 and by
   `monitor_app.py` carrying no diff.

Step 9 (Post-Implementation) then handles merge and archival as usual.

## Risk

### Code-health risk: low

- Two shared-library edits (`workflow_phase.render_phase`, `gate_ledger.compact_gate_summary`)
  are refactors whose outputs must not move; `ait monitor` and the board read both ·
  severity: low · → mitigation: none needed — test class 1 pins `render_phase`'s four
  outputs verbatim and the existing `compact_gate_summary` value tests
  (`test_gate_ledger_python_parser.py:153-197`, `test_monitor_gate_cache.py:86-122`)
  already assert the long form; both run in Verification step 1.
- `abbreviate_gate_summary` is a string transform over another function's output, so a
  new tail part could pass through unabbreviated · severity: low · → mitigation: none
  needed — both directions read `GATE_SUMMARY_TAIL`, the unknown-part fallback is
  verbatim-not-dropped, and test class 2 adds the drift guard.
- t1351 is `Ready` and edits the same method and the same 38-cell budget; landing later
  it could restate the arithmetic or reshape row 1 under this task's assertions ·
  severity: low · → mitigation: none needed — the "Coordination with t1351" section
  above defines the shared `_row_budget` / `_detail_budget` API, the docstring forward
  pointer, and the truncation-insensitive fixture rule, all delivered by this plan.

### Goal-achievement risk: low

- AC 7's live 40-column capture depends on a real tmux and on the fixture window
  resolving to a task with a gate ledger; a mis-set-up pane would show an ungated card
  and verify nothing · severity: low · → mitigation: none needed — Verification step 3
  uses t1479 itself, whose ledger carries real gate runs by implementation time, and
  the poll-on-a-different-signal discipline from `tests/test_board_header_row_live.py`
  applies.

No mitigation tasks or inline phases are proposed: every identified risk is discharged
by an explicit step of this plan (the `render_phase` pin, the drift guard, the t1351
hand-off contract, the live-capture recipe), so there is nothing left for a separate
mitigation task to do.
