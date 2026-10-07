---
Task: t1904_codex_update_prompt_0160_wording.md
Base branch: main
Output branch: main
---

# t1904 — `codex_update_prompt`: match the codex-cli 0.160 hint wording

## Context

`codex_update_prompt` (`.aitask-scripts/monitor/prompt_patterns.py:290-295`)
anchors on the dialog's last option row (`3. Skip until next version`), one
blank row, and the hint `Press enter to continue`. codex-cli 0.160.0 renders the
hint as `enter continue · esc skip` (measured live in t1900, stored as
`CODEX_0160_INLINE_UPDATE_PROMPT_RAW` / `CODEX_0160_INLINE_DISMISSED_UPDATE_RAW`
in `tests/review_loop_fixtures.py`). The dialog is therefore no longer
pattern-detected on followed panes (`ait monitor` reads an agent parked on it as
idle). The review loop still says `dialog` structurally, through the option row.

Stripped, the 0.160 tail is:
```
› 1. Update now (runs `npm install -g @openai/codex`)
  2. Skip
  3. Skip until next version

  enter continue · esc skip
```
The geometry (option 3, exactly one blank row, the hint) is unchanged, so one
alternation in the hint slot covers both versions. The same kind name keeps every
consumer (`DELIBERATELY_UNANCHORED_KINDS`, the characterization matrix, the
followed-pane kind) unchanged. A sibling pattern would add a second kind name
for the same dialog, so I'm not adding one.

## Implementation

### 1. `.aitask-scripts/monitor/prompt_patterns.py`
- Change the hint line of the `codex_update_prompt` regex to:
  `r"[ \t]*(?:Press enter to continue|enter continue · esc skip)[ \t]*$"`
  Keep the option-3 anchor, the single blank row, `(?m)`, and
  `skip_trailing_blank_rows=True`.
- Update the comment block. Say that the hint has two measured wordings:
  pre-0.160 `Press enter to continue`, and `enter continue · esc skip` on
  0.160.0 (t1900, inline shadow capture). The other anchors are unchanged.
  Extend the "hint alone is generic prose / sign-in screen" reasoning to both
  wordings. Keep the comment current-state only.

### 2. `.aitask-scripts/monitor/review_loop.py` (docstring only)
- `_codex_dialog_is_historical` docstring, lines ~719-724: replace "On 0.160 its
  hint wording no longer matches `codex_update_prompt`…" with the current
  state. Both the 0.154 and 0.160 dismissed dialogs now match the pattern, and
  this predicate is what keeps them reading ready.

### 3. `tests/review_loop_fixtures.py` (comment only)
- Lines ~305-307: replace the "does not match" sentence. The hint reads
  `enter continue · esc skip`, which `codex_update_prompt` matches (t1904).

### 4. `tests/test_prompt_detection.py` (followed-pane detection)
- Parameterize `_update_prompt_with_selection(option, tail=None)` so it can
  rewrite the selection marker on the 0.160 tail too (default tail = current
  behaviour).
- Add `_update_prompt_0160_tail()` = `strip_ansi(fx.CODEX_0160_INLINE_UPDATE_PROMPT_RAW)`.
- New `_check_codex_update_prompt_0160_detected`. It checks
  `awaiting_input_kind == "codex_update_prompt"` for: the tail as captured, the
  tail top-aligned with each `_UPDATE_PROMPT_MEASURED_BLANK_RUNS` run, the
  options 1/2/3 selected (top-aligned), and the `node` launcher command.
- In the same check, assert that `CODEX_0160_INLINE_DISMISSED_UPDATE_RAW`
  (stripped) is **not** awaiting. The 6-row window ends on the composer and
  status row, so the dismissed dialog in scrollback must not flag the pane.
- `_check_codex_update_prompt_negative_controls`: add the 0.160 hint variants.
  These are: the hint alone, the hint quoted inline in prose, the hint as a
  bullet, option and hint in a blockquote, option 3 and the hint with no blank
  row between them, and the sign-in onboarding tail ending in the new hint.
- `_check_codex_update_prompt_known_false_positive`: add the 0.160 geometry case
  (the same accepted limit).
- Register the new check in `main()`.

### 5. `tests/test_review_loop.py` (review loop)
- Replace `test_a_pattern_for_the_0160_wording_would_not_wedge_it`, which
  injected a stand-in pattern, with `test_the_shipped_pattern_matches_0160_without_wedging`.
  The new test uses the **shipped** pattern and checks four things:
  - the `codex_update_prompt` regex finds the 0.160 rows in both the live and
    the dismissed stripped captures;
  - the live capture reads `SHADOW_DIALOG`;
  - the dismissed capture reads `SHADOW_READY`, and `shadow_prompt_ready` is `True`;
  - as a negative control, with `dialog_is_historical=lambda *_: False` passed
    to `_composer_state` (the existing mutation idiom), the dismissed 0.160
    capture reads `SHADOW_DIALOG`. That shows the pattern now really matches it
    and that the predicate is what keeps it ready. Before this fix that control
    would have read READY.
- Update the `HISTORY` comment ("its wording matches") so it no longer implies
  that only the pre-0.160 wording matches.

### 6. `tests/test_minimonitor_concern_action.py` (end-to-end latch)
- Add a 0.160 twin of
  `test_a_dismissed_dialog_in_inline_scrollback_does_not_wedge_the_loop`.
  Captures are `[CODEX_0160_INLINE_UPDATE_PROMPT_RAW] + [CODEX_0160_INLINE_DISMISSED_UPDATE_RAW] * 40`,
  run through `_ticks_until_release`. The latch must release after the settle
  deadline. Negative control: with `_codex_dialog_is_historical` stubbed to
  `False` it must never release. That is the wedge the pattern would cause
  without t1900's predicate, now exercised on real 0.160 captures.

### Step 9
Post-implementation: commit the code, then archive via the standard Step 9 flow.

## Verification
- `python3 tests/test_prompt_detection.py`
- `bash tests/run_all_python_tests.sh --test-dir` is not needed. Run the
  touched modules directly:
  `~/.aitask/venv/bin/python -m pytest tests/test_review_loop.py tests/test_minimonitor_concern_action.py -q`
  (or unittest if pytest is unavailable).
- Mutation check, run by hand and not committed: revert the regex to the
  pre-0.160 hint. The new 0.160 detection check, the review-loop control and
  the minimonitor negative control must fail.
- Full suite: `bash tests/run_all_python_tests.sh`. Read the last line for the
  verdict.

## Risk

### Code-health risk: low
None identified. This is one alternation inside an existing anchored regex. The
geometry, the opt-in trim and the kind name are unchanged. Existing negative
controls and the new 0.160 ones pin the scope.

### Goal-achievement risk: low
None identified. The pattern is pinned against the committed live 0.160
capture, in both bottom-anchored and top-aligned geometry. Both consumers
(followed-pane window and review loop) are tested on the same fixtures.

## Final Implementation Notes
- **Actual work done:** The hint slot of `codex_update_prompt` now takes `(?:Press enter to continue|enter continue · esc skip)`, and the comment block records both measured wordings. Tests:
  - followed-pane detection matrix on the live 0.160 capture (as captured; top-aligned 14/20/40; options 1/2/3 selected; `node` launcher), with the dismissed 0.160 capture asserted not awaiting;
  - six 0.160 negative controls;
  - the known false positive covers both wordings;
  - the review-loop test now uses the shipped pattern, plus a predicate-off negative control;
  - an end-to-end minimonitor settle-latch test on the real 0.160 captures, plus its negative control.
- **Deviations from plan:** The `HISTORY` comment in `CodexHistoricalDialogTests` was left unchanged. It is accurate as it stands: it describes the pre-0.160 fixture, whose wording does match. The review-loop negative control became its own test method rather than an assertion inside the positive test.
- **Issues encountered:** t1902 was running in a concurrent session and held uncommitted hunks in `review_loop.py`, `review_loop_fixtures.py` and `test_review_loop.py`. My `review_loop.py` docstring rewrite sat in the same hunk as theirs. We coordinated over a cross-session message: t1902 committed only its own hunks through a temp index (c0da4acfe), and before committing I checked that the remaining diff in all six files was only t1904's.
- **Key decisions:** I extended the existing pattern instead of adding a sibling. One kind name for one dialog keeps every consumer unchanged: `DELIBERATELY_UNANCHORED_KINDS`, the characterization matrix, and the followed-pane kind. The mutation check was run in a scratch copy, so the shared working tree was never touched. With the regex reverted to the pre-0.160 hint, all 5 new or changed tests fail.
- **Upstream defects identified:** None
