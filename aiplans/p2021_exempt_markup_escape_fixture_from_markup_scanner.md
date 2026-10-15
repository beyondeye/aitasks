---
Task: t2021_exempt_markup_escape_fixture_from_markup_scanner.md
Base branch: main
Output branch: main
---

# t2021 — Keep the hostile title fixture scanned without tripping Rule C

## Context

`tests/test_monitor_markup_escape.py:69` (added by t2006) holds the deliberately
unescaped title `'Fix [/] and [dim]x[/dim]'`. The repo-wide Rule C scan in
`tests/test_textual_markup_colours.py` (`scan_repo_structure` →
`MarkupStructureScanTests::test_every_closing_tag_matches_an_open_tag`) gates any
single string expression that has a named close (`[/dim]`) and a candidate open
(`[dim]`), then parses it with `Content.from_markup`. This literal fails that
parse. Today it is the **only** finding in the tree (reproduced: `gated 179`, one
finding at `:69`), and it is the only failure in the full Python suite.

**Chosen fix: option (b) from the task. Split the literal with `+`.**
- `ast.parse` keeps `"a" + "b"` as a `BinOp` (probed), so the scanner sees two
  constants.
  - `"Fix [/] and "` has no named close, so the gate skips it.
  - `"[dim]x[/dim]"` is gated and parses cleanly.
  - The runtime value is byte-identical, so every consumer of `TITLES` is
    unaffected.
- The file **stays scanned** for Rules A, B and C. Its real markup (the
  `f"[bold]{…} (0)[/]"` templates) keeps its coverage.
- The same file already uses this shape at `NAMES[4]`: `"agent-" + "[/]x[dim]" * 5`.
- The split relies on the scanner judging each constant of a `+` chain on its
  own. That is **not** pinned today, so step 3 adds a pin.
  - The existing `test_gap_markup_assembled_across_expressions` scans
    `"[bold]" + name + "[/bolt]"`, where a **variable** separates the literals.
  - A future scanner that folded only constant-plus-constant `+` (the
    `Constant + Constant` BinOp) would close the fixture's gap and still leave
    that test green.
  - The repo scan itself would still fail loudly on the fixture, so nothing
    passes silently. But the gap test is meant to be the early, named signal,
    and today it does not cover this shape.

**Why not option (a), `SELF_REFERENTIAL_MODULES`:**
- It would take the 3rd of 3 allowed slots
  (`test_the_exclusion_list_stays_small`, `≤ 3`), leaving none for t2017's
  planned mirror tests.
- It would remove Rules A, B and C from the whole file.
- The file is about escaping user text, not about this defect class, which is
  the stated criterion for an exclusion.
- It is the blanket per-file exemption that the scanner's own comment warns
  against.

## Implementation

1. **`tests/test_monitor_markup_escape.py`, the `TITLES` list (line 69).** Replace
   the single literal with
   `"Fix [/] and " + "[dim]x[/dim]",` and add an aligned inline comment in the
   style of the neighbouring entries, e.g.
   `# split: one literal trips Rule C (test_textual_markup_colours.py)`.

2. **Same file: pin that the split fixture is still hostile.**
   - Add `from textual.markup import MarkupError  # noqa: E402` beside the
     existing `from textual.content import Content` import.
   - Add one test to `MarkupLiteralTests`:
     ```python
     def test_the_split_title_fixture_is_still_hostile(self):
         """TITLES[0] is built with `+` only so the repo-wide Rule C scan
         (tests/test_textual_markup_colours.py) does not read it as live
         markup. It must stay a string Textual refuses unescaped: escaping it
         to quiet the scan would remove the input this file exists to test."""
         with self.assertRaises(MarkupError):
             parse(TITLES[0])
     ```
   - The assertion must not contain the joined literal; that would re-trip Rule C.

3. **`tests/test_textual_markup_colours.py`: pin the exact constant-plus-constant
   gap.** This addresses the review concern.
   - In `StructureScannerDiscriminationTests`, "documented gaps" block, after
     `test_gap_markup_assembled_across_expressions`, add:
     ```python
     def test_gap_constant_only_concatenation_is_not_folded(self):
         """The hostile-fixture convention depends on this gap (t2021).

         tests/test_monitor_markup_escape.py builds its unparsable title with
         `+` so the repo scan does not read it as live markup. The
         variable-separated row above would keep passing under a scanner that
         folded constant-only `+`; this row would not.
         """
         source = 'x = "Fix [/] and " + "[dim]x[/dim]"'
         self.assertEqual([], self._scan(source))
         self.assertEqual(1, self._gated(source), "only the intact pair is gated")
         with self.assertRaises(Exception):
             Content.from_markup("Fix [/] and [dim]x[/dim]")
     ```
   - The test asserts quiet **and** why, as the block's header comment requires.
     The text is scanned piecewise (`gated == 1`), and the joined text really is
     unparsable, so the test cannot pass because of a malformed fixture.
     `assertRaises(Exception)` matches the sibling `test_gap_action_link_opening_tag`.
   - Module docstring, coverage table: that table is "one test per row" and is
     pinned by these tests. Add a row after the `"[bold]" + name + "[/bolt]"`
     row:
     `"Fix [/] and " + "[dim]x[/dim]" MISSED   (constant + constant)`.
   - Module docstring, "Not in scope", the "Markup assembled across
     expressions" bullet. Its current justification ("joining them needs
     dataflow analysis") is not true of constant-only `+`, which plain folding
     would join. Add one sentence:
     - constant-only `+` is not folded either;
     - that is relied on: it is how a hostile-input fixture stays scanned
       (`tests/test_monitor_markup_escape.py`, t2021);
     - it is pinned by `test_gap_constant_only_concatenation_is_not_folded`.

     Leave "Repo instances of a tag pair split that way: 1" unchanged. That
     count stays true, because this split separates a stray `[/]` from an
     intact pair rather than splitting a pair.

4. **`tests/test_textual_markup_colours.py`, `STRUCTURE_REMEDIES`.** Add one
   bullet after "Literal bracket". This text is the failure message the next
   author sees (t2017 will add more hostile fixtures). It says:
   - **Hostile-input fixture** → a test that deliberately feeds broken markup to
     the parser must keep it broken. Do not escape it.
   - Split it with `+`, so that the offending tag sits in a literal apart from
     the tags it fails to match (example: `tests/test_monitor_markup_escape.py`
     `TITLES`).
   - This relies on the gap pinned by
     `test_gap_constant_only_concatenation_is_not_folded`.
   - Do not add the file to `SELF_REFERENTIAL_MODULES`; that unscans the whole
     file.

   This file is itself in `SELF_REFERENTIAL_MODULES`, so neither the remedy text
   nor the new test's literals are scanned.

## Verification

- `~/.aitask/venv/bin/python tests/test_textual_markup_colours.py`: all pass,
  including:
  - the Rule C live scan (0 findings);
  - `test_the_structure_scan_is_not_vacuous`;
  - the waiver-hygiene / waiver-rot tests;
  - the discrimination and negative-control tests.
- Re-run the scan probe. Expected:
  - `scan_repo_structure()` has 0 findings and its gated count stays 179;
  - for `tests/test_monitor_markup_escape.py`, `scan_source_structure` still
    reports `gated 1` (the `"[dim]x[/dim]"` half), which shows the file is still
    scanned.
- Negative control for the scanner (no worktree edits): run
  `scan_source_structure` on a synthetic source holding the old single literal.
  It must report 1 finding. The same source with the `+` split must report 0.
- Negative control for the new gap pin: in-process, from the scratchpad, wrap
  `_markup_expressions` so that it folds constant-only `+` BinOps into one
  string.
  - `test_gap_constant_only_concatenation_is_not_folded` must then **fail**.
  - `test_gap_markup_assembled_across_expressions` must still **pass**.

  That is the discrimination the review asked for. The mutant lives only in the
  probe process, so no tracked file is edited.
- Negative control for the new pin:
  - `Content.from_markup` on an escaped variant (`"Fix \\[/] and [dim]x[/dim]"`)
    does **not** raise, so the pin fails if someone escapes the fixture.
  - The real `TITLES[0]` does raise.
- `~/.aitask/venv/bin/python tests/test_monitor_markup_escape.py`: all pass,
  including the new test.
- `bash tests/run_all_python_tests.sh`, run in the background. Read only the last
  line and expect `PYTHON SUITE: PASSED`. Several unrelated dirty files from
  other sessions are in the tree; attribute any failure before acting on it.
- Commit by path only: the two test files. The tree holds unrelated changes from
  other sessions.

## Step 9 (Post-Implementation)

This runs in current-branch mode, so nothing is merged. Archive with
`./.aitask-scripts/aitask_archive.sh 2021`, then run `./ait git push`. At
Step 8e, offer a note to t2017 (Implementing, plans hostile mirror fixtures)
naming the convention that landed in `STRUCTURE_REMEDIES`.

## Risk

### Code-health risk: low
- The fixture depends on Rule C not folding constant-only `+`. If that changes,
  the fixture trips again. The failure is loud, not silent:
  - the exact shape is pinned by the new
    `test_gap_constant_only_concatenation_is_not_folded` (step 3);
  - the variable-separated gap test does not cover this shape, which was a
    review finding;
  - the remedy text names the dependency.

  severity: low · → mitigation: none (addressed in-plan by steps 2–4)

### Goal-achievement risk: low
None identified.

## Final Implementation Notes
- **Actual work done:** Implemented steps 1–4 as planned.
  - `tests/test_monitor_markup_escape.py`: `TITLES[0]` is now
    `"Fix [/] and " + "[dim]x[/dim]"` (same runtime value, inline comment
    naming Rule C). Added `from textual.markup import MarkupError` and
    `MarkupLiteralTests::test_the_split_title_fixture_is_still_hostile`.
  - `tests/test_textual_markup_colours.py`: added
    `StructureScannerDiscriminationTests::test_gap_constant_only_concatenation_is_not_folded`.
    Added the coverage-table row `"Fix [/] and " + "[dim]x[/dim]" MISSED
    (constant + constant)`. Added a sentence to the "Markup assembled across
    expressions" bullet of "Not in scope", and a "Hostile-input fixture" bullet
    in `STRUCTURE_REMEDIES`.
- **Deviations from plan:** None. Step 3 (the exact-shape gap pin) came from a
  plan-review concern before approval. The concern: the existing
  `test_gap_markup_assembled_across_expressions` uses a variable-separated
  `"[bold]" + name + "[/bolt]"`, so a scanner folding only constant-only `+`
  would close the fixture's gap and still leave that test green.
- **Issues encountered:**
  - The full suite (`bash tests/run_all_python_tests.sh`) ended
    `PYTHON SUITE: FAILED (runner=pytest, exit=1)`: 9095 passed, 4 failed, all
    in `tests/test_monitor_frozen_filter.py::MinimonitorOwnPanelTests`.
  - These are not attributable to this change. Neither changed file is
    imported by that module, and during the 7-minute run another session was
    editing `.aitask-scripts/monitor/minimonitor_app.py`,
    `.aitask-scripts/monitor/monitor_shared.py` and
    `tests/test_monitor_frozen_filter.py` itself.
  - On rerun against the current tree with this change still in place, all
    72 tests in that file pass.
  - Both changed files pass in full: 48 tests and 9 tests.
- **Verification evidence:** probe run in-process from the scratchpad; no
  tracked file was mutated.
  - Live tree: `scan_repo_structure()` gives 0 findings, `gated 179`
    (unchanged). The escape file is still scanned (`gated 1`).
  - Scanner control: the old single literal gives 1 finding; the split form
    gives 0.
  - Hostility-pin control: the escaped variant `"Fix \\[/] and [dim]x[/dim]"`
    parses, so the pin would fail on an escape. The real `TITLES[0]` raises
    `MarkupError`.
  - Mutant: `_markup_expressions` was wrapped to fold constant-only `+`
    BinOps. Under it, `test_gap_constant_only_concatenation_is_not_folded`
    FAILS, `test_gap_markup_assembled_across_expressions` PASSES, and the real
    escape file shows 1 finding.
- **Key decisions:**
  - Chose option (b), splitting the literal, over (a), `SELF_REFERENTIAL_MODULES`.
    Option (a) would take the 3rd of 3 allowed slots
    (`test_the_exclusion_list_stays_small`) and remove Rules A, B and C from
    the whole file. The file is also not *about* the defect class.
  - The hostility pin avoids writing the joined literal, which would re-trip
    Rule C. The scanner file can hold the joined literal because it is itself
    in `SELF_REFERENTIAL_MODULES`.
- **Upstream defects identified:** None
