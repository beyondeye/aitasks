---
priority: high
effort: medium
depends: [t1636_1]
issue_type: enhancement
status: Ready
labels: [shadow, aitask_monitormini, concern_format]
gates: [risk_evaluated]
anchor: 1636
created_at: 2026-08-30 14:53
updated_at: 2026-08-30 14:53
---

## Context

Part of t1636 (shadow concern impact-vector model). Extends the pure parser to
derive the impact vector (`Improves:` / `Worsens:` / `Effort:`) from the
terminal trailer run, alongside the existing `Disposition:` / `Verified:`
derivation. Depends on t1636_1 (`concern_dimensions.py` — the closed vocabulary
and `derive_priority`). The parent plan
(`aiplans/p1636_shadow_concern_impact_vector_model.md`) settles the grammar
(decision 6) and the three-state Worsens shape (decision 5); follow it exactly.

Grammar (settled — decision 6):
- Dimension names: CLOSED alternation from `concern_dimensions`. A sentence
  with an unknown dimension fails to match AS A WHOLE SENTENCE and stays
  visible in display body + forwarded payload.
- Magnitudes: bounded-permissive — entry is `name` or `name(token)`,
  `token = \w{1,16}`. Recognised `high|medium|low` (case-insensitive)
  normalizes; unrecognised/absent → `""` (unspecified), NEVER `low` (degrading
  the worsen side would understate a cost). Dimension never dropped.
- Per-sentence atomicity, valid-suffix run: `_TRAILER_SPAN` matches the
  terminal run of VALID sentences; an invalid sentence terminates the run's
  extension, so a valid `Disposition:`/`Effort:` suffix after an invalid
  `Improves:` sentence is still parsed and the invalid sentence stays in the
  display body.

Field shape (settled — decision 5): `improves` / `worsens` are
`tuple[ImpactEntry, ...] | None` — `None` = sentence absent (NOT priced),
`()` = present and empty (`Worsens: nothing.` — priced as nothing). The
distinction IS the anti-overengineering mechanism; collapsing them deletes the
feature's point. `effort`: `str` (`high|medium|low` or `""`).

## Key Files to Modify

- `.aitask-scripts/monitor/concern_parser.py`:
  - `_TRAILER_SENTENCE` (~line 176): add the three sentence alternatives,
    built from `concern_dimensions` (sibling import with the same try/except
    flat-import fallback as `ansi_utils`, line 104 — the module stays pure).
  - `Concern` NamedTuple: APPEND `improves`, `worsens`, `effort` after the
    existing fields, with defaults — positional construction of existing call
    sites must be unaffected.
  - `_parse_trailer`: return the new fields. `display_body()` needs NO new
    stripping logic (it already removes the whole matched span).
- `tests/test_concern_parser.py`: extend `TestDispositionDerivation` (line 568)
  + a new vector-grammar test class.

## Reference Files for Patterns

- `concern_parser.py:176-192` — existing trailer regex trio
  (`_TRAILER_SENTENCE`, `_TRAILER_SPAN`, per-field extractors).
- `tests/test_concern_parser.py::TestDispositionDerivation` — trailer test
  shapes, including "body stays canonical / forwarding byte-identical".
- `tests/test_concern_body_display_contract.py` — the FORWARD/DISPLAY
  role-map guard; it must stay green UNTOUCHED.

## Implementation Plan

1. FIRST (risk mitigation `characterize_parser_backcompat`, from the parent
   plan): write the characterization test pinning the FIVE-FIELD PROJECTION
   CONTRACT, and observe it PASS against unmodified `concern_parser.py` before
   any edit — expected values as recorded literals that do NOT change when the
   implementation lands. Pins: (a) for a no-trailer block and a
   Disposition:/Verified:-only block, each parsed Concern's projection onto
   (`priority`, `region`, `body`, `disposition`, `verdict`) equals today's
   output; (b) five-argument positional construction still populates exactly
   those five fields; (c) `display_body()` and `build_clipboard_payload` are
   byte-identical. (NOT whole-tuple equality — appended fields change tuple
   length/equality by construction; that is documented, not defended.)
2. SECOND (risk mitigation `discriminate_priced_vs_unpriced_worsens`): before
   choosing the field shape's implementation, write the test that fails unless
   the parser distinguishes THREE states: `Worsens: nothing.` (priced, `()`),
   absent sentence (`None`), populated list. Name all three explicitly so a
   two-state implementation cannot satisfy it.
3. Implement the grammar extension per the settled decisions above.
4. Add the vector-grammar tests: three-state Worsens; missing + unknown
   magnitude; unknown dimension on each side; invalid sentence followed by
   valid suffix; fully valid run fully stripped from display; `derive_priority`
   edges (empty, all-unknown); clipboard forwards `.body` verbatim.

## Verification

- `python -m pytest tests/test_concern_parser.py tests/test_concern_body_display_contract.py`
- `bash tests/run_all_python_tests.sh --test-dir tests` — read only the last
  line (`PYTHON SUITE: PASSED|FAILED`).
