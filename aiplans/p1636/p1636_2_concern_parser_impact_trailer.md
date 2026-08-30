---
Task: t1636_2_concern_parser_impact_trailer.md
Parent Task: aitasks/t1636_shadow_concern_impact_vector_model.md
Sibling Tasks: aitasks/t1636/t1636_1_concern_dimension_vocabulary_module.md, aitasks/t1636/t1636_3_producers_emit_impact_trailer.md, aitasks/t1636/t1636_4_picker_trade_profile_rendering.md, aitasks/t1636/t1636_5_delta_scoped_auto_recheck.md
Archived Sibling Plans: aiplans/archived/p1636/p1636_*_*.md
Branch: main
Base branch: main
Output branch: main
---

# p1636_2 — Parser: impact-trailer extension

Extends `.aitask-scripts/monitor/concern_parser.py` to derive `improves` /
`worsens` / `effort` from the terminal trailer run. Depends on t1636_1
(`concern_dimensions.py`). Parent plan decisions 5 (three-state Worsens) and 6
(grammar: closed dimensions, bounded-permissive magnitudes, per-sentence
atomicity with valid-suffix runs) are binding.

## Steps

1. **[characterize_parser_backcompat — risk mitigation, FIRST, before any
   parser edit]** Add to `tests/test_concern_parser.py` a characterization
   class pinning the **five-field projection contract**, and run it to
   **observed-pass against unmodified `concern_parser.py`** before step 3.
   Expected values are recorded literals that do NOT change when the
   implementation lands. Pins, for (a) a block with no trailer and (b) a block
   with a `Disposition: follow-up. Verified: PLAUSIBLE.`-only trailer:
   - each parsed `Concern`'s projection onto (`priority`, `region`, `body`,
     `disposition`, `verdict`) equals today's exact output (literal tuples in
     the test);
   - `Concern("high", "r", "b", "blocking", "CONFIRMED")` five-argument
     positional construction populates exactly those five fields;
   - `display_body()` and `build_clipboard_payload([...])` outputs are
     byte-identical literals.
   (Whole-tuple equality is deliberately NOT pinned — appending fields changes
   tuple length/equality by construction; note that in the test docstring.)

2. **[discriminate_priced_vs_unpriced_worsens — risk mitigation, before the
   field shape is implemented]** Write the test that fails unless the parser
   distinguishes **three** states, all named explicitly:
   - `… Worsens: nothing. …` → `worsens == ()` (priced, empty);
   - no `Worsens:` sentence at all → `worsens is None` (not priced);
   - `… Worsens: simplicity(low). …` → populated tuple.
   A two-state implementation (e.g. empty-vs-populated) must fail it.

3. **Implement the grammar** in `concern_parser.py`:
   - `ImpactEntry = NamedTuple("ImpactEntry", [("dimension", str), ("magnitude", str)])`
     — magnitude already normalized (`""` = unspecified).
   - Import `concern_dimensions` as a sibling with the same try/except
     relative/flat fallback used for `ansi_utils` (line ~104); the module
     stays pure.
   - Extend `_TRAILER_SENTENCE` with three alternatives built from
     `concern_dimensions.dimensions_pipe()`:
     - `Improves: <entry-list>` / `Worsens: (nothing|<entry-list>)` /
       `Effort: \w{1,16}`;
     - `<entry-list>` = comma-separated `name(?:\(\w{1,16}\))?` where `name`
       is the **closed** alternation — an unknown dimension fails the whole
       sentence (it stays in the body/display, the chosen visible failure
       mode);
     - keep `_TRAILER_SPAN = (?:\s*SENTENCE)+\s*$` — terminal anchoring and
       free sentence order preserved verbatim; an invalid sentence simply
       isn't part of the matched suffix run.
   - Append to `Concern`: `improves: tuple | None = None`,
     `worsens: tuple | None = None`, `effort: str = ""` — **after** the
     existing fields, defaults set, docstring noting `None` = sentence absent
     vs `()` = `Worsens: nothing.`.
   - Extend `_parse_trailer` to return `(disposition, verdict, improves,
     worsens, effort)`: extract each sentence from the matched trailer span
     with per-sentence regexes (mirror `_DISPOSITION_IN_TRAILER`);
     `normalize_magnitude` each entry's token; `Effort:` token normalized the
     same way (`""` when unrecognized).
   - `display_body()` — no change needed: it already strips the whole matched
     span. Verify via tests that a fully valid run (all five sentence kinds)
     is fully stripped, and an invalid `Improves:` sentence before a valid
     suffix stays visible.

4. **Vector-grammar test class** (beyond steps 1–2): missing magnitude
   (`robustness` bare → `("robustness","")`); unknown magnitude
   (`robustness(extreme)` → `("robustness","")` — never `low`); unknown
   dimension on each side (whole sentence unparsed, visible in
   `display_body()`, valid suffix still parsed); sentence-order freedom
   (Effort before Improves etc.); multi-entry lists; `derive_priority`
   integration (`from concern_dimensions import derive_priority` over parsed
   `improves`); clipboard forwards `.body` verbatim with the full trailer.

5. **Contract sweeps**: `tests/test_concern_body_display_contract.py` must
   stay green **untouched** (its role map already governs `.body` vs
   `display_body()`); the docstring format table in `concern_parser.py` gains
   the new derived fields mention (keep the marker-grammar claims unchanged).

## Verification

- `python -m pytest tests/test_concern_parser.py tests/test_concern_body_display_contract.py tests/test_concern_dimensions.py`
- Step 1's class observed passing **before** step 3's first edit (record the
  run in the Final Implementation Notes).
- `bash tests/run_all_python_tests.sh --test-dir tests`; read only the last
  line.

## Post-Implementation

Standard Step 9. Note for t1636_3/_4/_5: the new fields and `ImpactEntry` are
the consumer surface; do not add consumers here.
