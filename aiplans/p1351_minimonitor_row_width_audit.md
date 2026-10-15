---
Task: t1351_minimonitor_row_width_audit.md
Branch: main
Base branch: main
Output branch: main
---

# t1351 — Minimonitor row-width audit

## Context

Minimonitor's agent row (row 1 of a card) overflows its pane. A row that
overflows does not get clipped: `Static` wraps it, so each overflowing agent
card costs an extra screen row (t1326 capture: `PROMPT` on one line and `123s`
on the next). The task asks for three things: an audit across every glyph
combination, a written column budget **in cells**, and a recorded decision on
what gives way first. Rich clips by cell, so it also asks to replace the
`len()`-based caps (which count code points) in `_agent_card_text` /
`_other_card_text` with cell-aware truncation.

**Measured during planning (these change the picture the task body describes):**

1. **The list's scrollbar costs 2 cells.** `#mini-pane-list` is a
   `VerticalScroll` whose scrollbar uses Textual's default width of 2 and
   appears once the list overflows. Probe with the real CSS at 40×12: with no
   scrollbar the card content is 38 cells; with a scrollbar it is **36**, and a
   37- or 38-cell row wraps to 2 lines. "~38 usable columns" is true only
   while the list does not scroll. The detail rows from t1479 (`_detail_budget`
   = 36 plus a 2-cell indent = 38) have the same flaw.
2. **Today's worst case is 39 cells.** `☆ ● ≈ ` (6) + name (20) + gap (2) +
   `PROMPT 999s` (11). It wraps even without a scrollbar. Since t1996 the status
   is bounded at 11 cells (note from t1996, acknowledged).
3. **The task id is at the end of the name.** Launch names are
   `agent-pick-<id>`, `agent-resume-<id>`, `agent-qa-<id>`, … At a 36-cell
   budget, clipping the tail gives `agent-pick-1351_…`, which loses the child
   number.
4. **Minimonitor never renders `◆!`.** `format_shadow_glyph` is called without
   `has_concerns`; only `ait monitor` passes it. The budget is still computed
   from the row's actual prefix, so `◆!` would cost one name cell if it ever
   appears.

**User decisions (AskUserQuestion during planning):**
- **What gives way:** agent rows show the window name **without the matched
  agent prefix** (`agent-pick-1351_12` → `pick-1351_12`). Every row in the
  agent section has that prefix, because the prefix is what made it an agent.
  The tail is clipped only if the name still does not fit. The docked "this
  agent" panel, the `other` section and `ait monitor` keep full names.
- **Scrollbar:** always reserve its 2 columns, for row 1 and for the detail rows.

## The budget (to be written once, in the existing block at `minimonitor_app.py` ~L150)

Width W = `target_width` (default 40). All values are terminal cells.

```
W − 2 (MiniPaneCard padding: 0 1) − 2 (#mini-pane-list scrollbar, always reserved)
  = 36   row budget      _row_budget(W)
  − 2    "  " indent of the detail rows
  = 34   detail budget   _detail_budget(W)

Row 1, live agent:  <mark>␠<dot>[␠<shadow>]␠<glyph>␠<name>␠␠<status>
                    prefix = 6 | 8 with ◆ | 9 with ◆! (ait monitor only)
                    status reserved at PANE_STATUS_MAX_CELLS = 11 (`PROMPT 999s`)
                    name   = 36 − prefix − 2 − 11 = 17 | 15 | 14
Row 1, parked:      P␠<name>␠␠parked          name = 36 − 2 − 8 = 26
Row 1, frozen:      <mark>F␠<name>␠␠frozen    name = 36 − 3 − 8 = 25
Row 1, other:       ␠␠○␠<name>␠␠<cmd ≤ 10>    name = 36 − 4 − 2 − 10 = 20
Title row:          ␠␠<title>                 title ≤ min(30, detail budget) = 30
Gate/phase row:     ␠␠<merged>                ≤ detail budget = 34
```

**Shed order (the recorded decision):**
1. Agent rows never show the agent prefix. It is redundant, so dropping it costs
   no information.
2. A glyph added to row 1 is paid for by the **name's tail**. This happens
   automatically, because the name budget is computed from the row's own
   rendered prefix and never restated as a constant. The status is reserved at
   its bound, not its current width, so a name does not re-truncate as the
   elapsed counter grows or as the agent flips between Active and IDLE.
3. **Floor:** at the default width, the widest live prefix (9) must leave at
   least `_MIN_NAME_CELLS = 12` name cells. That fits `pick-NNNN_NN`, the
   commonest launch name with a 4-digit id and a 2-digit child. A test enforces
   it. A glyph that breaks the floor sheds **status verbosity** (the elapsed
   counter) next, never a second line. A second line costs a whole row per
   agent, and rows are this pane's scarce resource (the same reason t1479
   merged the gate and phase rows). Shedding the counter is a recorded policy
   only; no current combination reaches the floor, so no code for it ships.
4. No floor below that: at a configured width too narrow for the fixed parts,
   the name renders empty and the row may wrap. Rejecting an absurd width
   belongs at the config seam, the same rule `_detail_budget` already states.

The assumption is a narrow-ambiguous-width terminal: ★ ☆ ● ◆ ≈ … ○ are East
Asian Ambiguous, and Rich `cell_len` counts each as 1. This goes in the block
as a stated assumption.

**Width source: the configured `target_width`.** This matches the task's
explicit 40-column acceptance target and the existing `_detail_budget`.
`_maybe_pin_width` re-pins only a pane *wider* than the target, so a window too
narrow for the target leaves the real pane narrower, and these budgets
overshoot it. That case is out of this task's acceptance and becomes a planned
`after` follow-up (see `## Risk`, `budget_actual_pane_width`). The budget
block's comment names that limitation and the follow-up. The width-32/60
matrix cases in step 7 test only the target-derived arithmetic; they set the
target to that width and cannot expose the mismatch.

## Implementation steps

1. **Write the red tests first.** Create `tests/test_minimonitor_row_budget.py`
   (step 7 has the full content). Run it against the unchanged code and record
   the failures. Expected red: the composited worst-case rows wrap, the CJK
   rows overflow, and the prefix and scrollbar-constant tests error because the
   new symbols do not exist yet. Also run the scratch live-capture script
   (Verification §2) against the unchanged code, so a **pre-fix** real-tmux
   capture shows the wrap.

2. **`.aitask-scripts/monitor/monitor_shared.py`:** add
   `PANE_STATUS_MAX_CELLS = 11` beside `format_pane_status`, with a comment
   deriving it (`"PROMPT "` + the 4-character cap of `format_elapsed_compact`).
   Point the docstrings of `format_elapsed_compact` and `format_pane_status` at
   the constant instead of the literal 11.

3. **`.aitask-scripts/monitor/monitor_core.py`:** factor out the prefix match so
   classification and display cannot disagree:
   - `match_agent_prefix(window_name, prefixes) -> str | None`: the first
     prefix in list order that `window_name` starts with. This is exactly the
     loop in `classify_pane`.
   - `agent_display_name(window_name, prefixes) -> str`: `window_name` minus the
     matched prefix. It returns `window_name` unchanged when nothing matches,
     when the match is empty, or when stripping would leave an empty name (a
     window named exactly `agent-`).
   - `classify_pane` calls `match_agent_prefix(...) is not None`. This is a
     mechanical swap with no behaviour change.

4. **`.aitask-scripts/monitor/minimonitor_app.py`, budget block (~L150–185):**
   - add `_LIST_SCROLLBAR = 2`; `_row_budget(W) = max(0, W − _ROW_PADDING −
     _LIST_SCROLLBAR)`; `_detail_budget(W) = max(0, _row_budget(W) −
     _DETAIL_INDENT)`. Keep the clamp-at-zero rationale.
   - add `_NAME_GAP = 2`, `_OTHER_CMD_CELLS = 10`, `_TITLE_MAX_CELLS = 30` and
     `_MIN_NAME_CELLS = 12`, each with a one-line why.
   - add `_name_room(prefix_markup: str, reserve: int, target_width: int) ->
     int`, which returns `_row_budget − cell_len(Text.from_markup(prefix).plain)
     − _NAME_GAP − reserve` (may be ≤ 0; `_clip` already handles that).
   - rewrite the block's comment to hold the arithmetic and shed order above.
     This is now the single source. Update `_row_budget`'s docstring, which
     currently hands row 1 to t1351.
   - CSS: `#mini-pane-list { height: 1fr; scrollbar-size-vertical: 2; }`, with a
     comment that `_LIST_SCROLLBAR` mirrors it. This makes the width explicit
     instead of relying on Textual's default.

5. **`.aitask-scripts/monitor/minimonitor_app.py`, rows:**
   - `_display_name(self, snap) -> str`: read `getattr(self._monitor,
     "agent_prefixes", None)`. If it is not a list or tuple (no monitor yet,
     test stubs), return the full window name, so nothing is stripped when the
     classifier's input is unknown. Otherwise return `agent_display_name(...)`.
   - `_agent_card_text`, all three row shapes. Build the prefix markup first,
     then `name = escape(_clip(display_name, _name_room(prefix, reserve,
     self._target_width)))`. The reserve is `PANE_STATUS_MAX_CELLS` for live
     rows and the cell width of the literal `frozen` / `parked` suffix for
     those rows. Clip **before** escaping, the same pattern `_own_header_text`
     uses at L259. Window names are tmux user input, and an unescaped `[/]`
     would corrupt the row's markup and make the budget assertion meaningless.
     Replace the comment at ~L2371 with a pointer to the budget block.
   - Title: `escape(_clip(info.title, min(_TITLE_MAX_CELLS,
     _detail_budget(self._target_width))))` in place of the `len(title) > 30`
     cap.
   - `_other_card_text`: `cmd = _clip(cmd, _OTHER_CMD_CELLS)`; name clipped to
     `_name_room("  [dim]○[/] ", _OTHER_CMD_CELLS, self._target_width)`; both
     escaped. Its docstring drops the restated table and the "assumes
     single-cell characters" paragraph, which would no longer be true, and
     points at the block instead.

6. **Update the existing tests that pin the old arithmetic:**
   - `tests/test_minimonitor_gate_phase_row.py`: `_ROW_WIDTH_BUDGET = 36`,
     `_DETAIL_BUDGET = 34`, and the comment names the scrollbar. Width-10 pins
     change to `_detail_budget(10) == 4` and `_row_budget(10) == 6`;
     `_detail_budget(3)` stays 0. Probed during planning:
     `format_gate_phase_row("", "2/2 pass", 4) == "2/2"`, so the gates-only
     width-10 case is unchanged.
   - `tests/test_minimonitor_other_section.py`: `_ROW_WIDTH_BUDGET = 36`;
     `test_row_fits_the_column_budget` gains a double-width name and command
     case (`"漢" * 30`, `"字" * 30`), and its docstring's deferral note goes.
   - Run every `tests/test_minimonitor_*.py` and every
     `tests/test_monitor_*.py` that renders minimonitor cards. Fix any
     assertion that pinned a name clipped at 20 code points, recording each
     change in Final Implementation Notes.

7. **New `tests/test_minimonitor_row_budget.py`.** Self-contained unittest,
   using the env scrub and `sys.path` pattern of
   `test_minimonitor_other_section.py`.
   - `StatusBoundTests`: sweep `format_pane_status` over awaiting, completed,
     idle and active at elapsed values 0, 9, 10, 99, 100, 999, 1000, 14400,
     14459, 14460, 10⁹. Assert `max(cell_len(plain)) == PANE_STATUS_MAX_CELLS`
     (equality, so the reserve is tight, not just safe).
   - `PrefixTests`: `agent_display_name` strips the first matching prefix in
     list order, returns the full name for a prefix-only name, no match, or an
     empty prefix, and handles custom multi-prefix lists. An agreement table:
     for every case, `classify_pane(name) is AGENT` ⇔ `match_agent_prefix(name,
     prefixes) is not None`, using a real `TmuxMonitor` built with explicit
     prefixes (constructor only; check that it stays off tmux).
   - `AgentRowMatrixTests` (render-string level, a `__new__` stub like
     `_gated_app`, with `agent_prefixes=["agent-"]` on the stub monitor). The
     product is mark {none, priority} × shadow {absent, ◆, ◆! via patching
     `mm.format_shadow_glyph`} × compare {stripped, raw} × override {F, T} ×
     status {Active, IDLE, PROMPT, DONE at 999s} × name {`agent-pick-1351_12`,
     `agent-` + 60 ASCII, `agent-` + 30 × `漢`, an odd-boundary mix `agent-a漢漢…`,
     `agent-[/]x[dim]` × 5} × width {40, 32, 60}. For each case:
     `cell_len(plain line 1) ≤ _row_budget(W)`; the rendered name equals the
     display name when it fits, and otherwise ends in `…`; the plain text
     contains no `agent-` prefix.
     Plus parked and frozen rows over the same names and widths.
   - `NameFloorTests`: `_name_room(widest live prefix with ◆!,
     PANE_STATUS_MAX_CELLS, 40) >= _MIN_NAME_CELLS`. This is the test the next
     glyph must pass. Also check that `pick-1351_12` survives whole in the
     shadowed worst case at width 40.
   - `ScrollbarConstantTests`: mount the real app and assert that
     `#mini-pane-list`'s `styles.scrollbar_size_vertical == mm._LIST_SCROLLBAR`.
   - `CompositedRowTests` (the AC's composited-screen check). Host: a subclass
     of the **real** `MiniMonitorApp` (real `compose` and CSS, neutralised the
     same way as `_ListHost` / `_RefreshHost` in
     `tests/test_minimonitor_scroll_preservation.py`), with stubbed
     collaborators: snapshots awaiting input at `idle_seconds=999`, a shadow
     snapshot, compare mode overridden, `_mark_kind` → priority, plus a task
     cache and gate cache that give every card a CJK title and a long merged
     gate/phase row. Each card is therefore 3 rows. **The widest combination is
     forced explicitly.** Production minimonitor never passes `has_concerns`, so
     an ordinary shadow snapshot would render only `◆`. The fixture therefore
     patches `mm.format_shadow_glyph` with a wrapper that delegates to the real
     formatter with `has_concerns=True`. A precondition asserts that `◆!`
     appears on the composited screen, so the 9-cell prefix really is what was
     measured. Drive `_refresh_data()` and settle. Two scenarios:
     (a) 3 agents at 40×24. Precondition: no scrollbar is visible.
     (b) 30 agents at 40×24. Precondition: the scrollbar **is** visible.
     The preconditions make each scenario non-vacuous.
     For every visible card, assert `card.size.height == 3`, which means
     nothing wrapped. Also assert that the composited first row of the card
     (`render_strips()` at the card's region, rstripped) equals the expected
     plain line 1 exactly, which means nothing was clipped or ellipsised by
     Rich. Names cover `agent-pick-1351_12`, a long ASCII name and a CJK name.

8. **Docs:** `website/content/docs/tuis/minimonitor/how-to.md`:
   - L47: "The agent window name without the agent prefix (`agent-pick-42`
     shows as `pick-42`), shortened with `…` when it does not fit the row".
   - L330–331, the frozen example: `☆F pick-1705  frozen` / `★F qa-1699  frozen`.
   - Then run `cd website && python3 check_links.py --build`.

9. **Lint and suite:** `shellcheck` is not needed, since no shell changes.
   Run the new test file and the touched or affected test modules individually,
   then `bash tests/run_all_python_tests.sh` once, reading only the last line
   for the verdict.

## Verification

1. `python3 tests/test_minimonitor_row_budget.py`: red before step 2, green
   after. Same for the two updated test modules and every other
   `tests/test_minimonitor_*.py`.
2. **Real tmux capture at 40 columns** (an AC). A scratch script in the
   session scratchpad runs the step-7 composited host with `App.run()` in a
   real tmux pane on a private `-L` socket (pane pinned to 40 columns, the
   isolation pattern of `tests/test_minimonitor_bottom_pin_live.py`), then
   runs `capture-pane -p`. The host applies the same `◆!` patch as step 7, so
   the capture shows the widest combination: `★ ● ◆! ≈ <name>  PROMPT 999s`.
   Two runs: 3 agents (no scrollbar) and 30 agents (scrollbar), before and
   after the change. Pass criteria: post-fix, every card is exactly 3 lines
   and `◆!` is visible in the capture; pre-fix, the wrap reproduces. The
   script and all captures go verbatim into Final Implementation Notes,
   because they close the AC and must be durable.
3. `website/check_links.py --build` passes.
4. `bash tests/run_all_python_tests.sh`: last line `PYTHON SUITE: PASSED`.

## Risk

### Code-health risk: low
- Shrinking `_detail_budget` by the scrollbar's 2 cells moves the gate/phase row's shed point at every width, and t1479's pinned values change · severity: low · → mitigation: none (covered in-plan: step 6 restates the new arithmetic in the pins, and step 7's composited 3-row cards check the detail row inside a scrolling list)
- Routing `classify_pane` through the new `match_agent_prefix` could misclassify panes in both monitors if the swap is not exact · severity: low · → mitigation: none (covered in-plan: the step 7 agreement table runs against a real `TmuxMonitor`, and the existing classify-dependent suites run in step 9)

### Goal-achievement risk: medium
- Budgets read the configured `target_width`, but `_maybe_pin_width` only shrinks a pane that is wider than the target. When the window is too narrow, the real pane stays narrower (e.g. target 40, pane 32: a scrolling card has 28 cells while rows are built for 36), so rows still wrap there · severity: medium · → mitigation: budget_actual_pane_width
- The budget counts ★ ☆ ● ◆ ≈ … ○ as 1 cell each. A terminal configured to render East Asian Ambiguous characters as wide would still overflow · severity: low · → mitigation: none (stated as an explicit assumption in the budget block; the real-tmux capture in Verification §2 confirms the standard-locale case the AC asks for)
- Headless compositing could disagree with a real terminal · severity: low · → mitigation: none (covered in-plan: Verification §2 captures from a real tmux pane both before and after the change, with `◆!` forced in both)

### Planned mitigations
- timing: after | name: budget_actual_pane_width | type: bug | priority: medium | effort: medium | inline_risk: medium | added_complexity: medium | addresses: goal-achievement — rows still wrap when the real pane is narrower than the configured target | desc: budget minimonitor row and detail text against the available content width capped by target_width, rebuild row text when the pane width changes, and test configured width 40 with actual pane width 32 (scrolling and non-scrolling)

## Step 9 reference

Current-branch mode under profile `fast`: no worktree and no merge. Step 9
runs the gate orchestrator (`risk_evaluated` is active) and then archives with
`aitask_archive.sh 1351`.
