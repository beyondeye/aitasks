---
priority: medium
effort: low
depends: []
issue_type: bug
status: Ready
labels: [test_infrastructure, tui]
gates: [risk_evaluated]
anchor: 1794
followup_kind: upstream_defect
created_at: 2026-09-20 09:00
updated_at: 2026-09-20 09:00
---

## Origin

Spawned from t1794_7 during Step 8b review.

## Upstream defect

- `tests/test_mark_glyphs_single_source.py:283 — test_no_waiver_has_gone_stale checks the raw file text, so a waiver stays "earning its place" on a docstring occurrence even though rule 2 excludes docstrings; a waiver can therefore outlive every literal it waives`

## Diagnostic context

`test_mark_glyphs_single_source.py` enforces that the multi-select mark
(`✓`/`□`) has one authority (`lib/mark_glyphs.py`). Rule 2 flags a ratified
glyph in a **string constant** and **excludes docstrings**
(`_docstring_nodes`). `ALLOWED_LITERALS` waives a per-file glyph with a written
reason, and `test_no_waiver_has_gone_stale` is supposed to retire a waiver whose
literal is gone — its docstring says "A waiver whose literal no longer occurs is
an exception quietly accumulating."

But that check reads `(SCRIPTS / rel).read_text()` and asserts the glyph is
somewhere in that text. Docstrings and comments count. So the two halves
disagree about what a "literal" is: the scanner ignores docstrings, the
staleness check does not.

Observed in t1794_7: the board's `✓` waiver covered the follow-up-kind picker's
tick and the gate detail's `✓ <gate> — passed` row. Both moved to
`board/board_detail_screen.py`, leaving `aitask_board.py` with `✓` only in two
docstrings (`:576`, `:4674`). The waiver then waived nothing, but
`test_no_waiver_has_gone_stale` stayed green on those docstrings. It was retired
by hand after grepping; nothing would have reported it, and the same silence may
apply to the `RE_EXPORTS` sibling check.

## Suggested fix

Make the staleness check use the same notion of "literal" as the scanner it
guards: reuse the rule-2 walk (AST string constants minus `_docstring_nodes`)
and assert the waived glyph occurs in at least one **scanned** literal of that
file. Add a negative control: a file whose only occurrence is a docstring must
fail the staleness check (today it passes). Check whether
`test_no_reexport_waiver_has_gone_stale` has the same gap.
