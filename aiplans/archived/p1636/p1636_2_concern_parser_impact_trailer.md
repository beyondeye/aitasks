---
Task: t1636_2_concern_parser_impact_trailer.md
Parent Task: aitasks/t1636_shadow_concern_impact_vector_model.md
Sibling Tasks: aitasks/t1636/t1636_1_concern_dimension_vocabulary_module.md, aitasks/t1636/t1636_3_producers_emit_impact_trailer.md, aitasks/t1636/t1636_4_picker_trade_profile_rendering.md, aitasks/t1636/t1636_5_delta_scoped_auto_recheck.md
Archived Sibling Plans: aiplans/archived/p1636/p1636_*_*.md
Branch: main
Base branch: main
Output branch: main
plan_verified:
  - claudecode/opus5 @ 2026-08-30 17:00
---

# p1636_2 — Parser: impact-trailer extension

## Context

The shadow agent classifies every concern on a single, undefined `high/medium/low`
severity scale. t1636 replaces that with a **signed impact vector over a closed
quality-dimension vocabulary** — the improve side and the worsen side drawn from
the *same* dimensions — plus a separate one-time-cost `Effort:` scalar, so a
concern prices its own suggestion instead of being a pure demand with
externalised costs.

t1636_1 landed the vocabulary module
(`.aitask-scripts/monitor/concern_dimensions.py`) and the prose contract
(`concern-format.md` §"Derived fields: the impact vector"). **This child is the
consumer surface**: it extends `.aitask-scripts/monitor/concern_parser.py` to
derive `improves` / `worsens` / `effort` from the terminal trailer run, alongside
the existing `Disposition:` / `Verified:` derivation. It adds **no** producers
(t1636_3) and **no** UI (t1636_4) — only the parsed fields those consume.

Parent-plan decisions 5 (three-state Worsens) and 6 (grammar) are binding.

## Verification findings (this re-verification pass)

The plan was re-verified against the current tree. Baseline
`tests/test_concern_parser.py` + `test_concern_body_display_contract.py` +
`test_concern_dimensions.py`: **169 passed**. The design was probed against the
real vocabulary and confirmed to behave exactly as specified — including
per-sentence atomicity (`Text. Improves: bogus(x). Disposition: blocking.` strips
only ` Disposition: blocking.` and leaves the invalid sentence visible). Three
things the plan did not state:

1. **`_TRAILER_SPAN` carries `re.IGNORECASE`, so dimension names match
   case-insensitively too.** `Improves: Robustness(High).` matches the span and
   is therefore *stripped from the display body* — but a naive extractor stores
   `("Robustness", "")`, a name outside the closed vocabulary, for text the user
   can no longer see. The dimension name **must be lowercased** when the entry is
   built. This is the established convention, not a new one: `_parse_trailer`
   already does `.lower()` for disposition and `.upper()` for verdict.
2. **Duplicate sentences: first wins.** `Disposition: blocking. Disposition:
   informational.` already derives `blocking` (the `.search()` shape). The new
   per-sentence extractors use the same shape, so they inherit it — pin it rather
   than leave it open.
3. **An empty or trailing-comma entry list fails the sentence.** `Improves: .`
   and `Improves: goal,` do not match, so they stay visible. `improves` can
   therefore only ever be `None` or non-empty — `()` is reachable **only** via
   `Worsens: nothing.`, which is precisely the three-state mechanism.

## Steps

**Step 0 — durable plan first.** These findings exist only in the approved
preview until the plan is externalized. The Step-6 externalize call runs with
`--force` (mandatory on the verify path — `plan-externalization.md:125`: without
it the helper short-circuits with `PLAN_EXISTS` and the revisions never reach
`aiplans/`), replacing `aiplans/p1636/p1636_2_concern_parser_impact_trailer.md`
and committing it **before step 1**. No code is written until
`OVERWRITTEN:` is observed — otherwise t1636_3 / _4 / _5 would inherit a plan
whose constraints are absent from the audit trail.

### Pre-phase (risk mitigations)

1. **[`characterize_parser_backcompat`]** Add to `tests/test_concern_parser.py` a
   characterization class pinning the **five-field projection contract**, and run
   it to **observed-pass against unmodified `concern_parser.py` before step 3
   touches anything**. Expected values are recorded literals that do NOT change
   when the implementation lands. Pins, for (a) a block with no trailer and (b) a
   block with a `Disposition: follow-up. Verified: PLAUSIBLE.`-only trailer:
   - each parsed `Concern`'s projection onto (`priority`, `region`, `body`,
     `disposition`, `verdict`) equals today's exact output (literal tuples);
   - `Concern("high", "r", "b", "blocking", "CONFIRMED")` five-argument
     positional construction populates exactly those five fields;
   - `display_body()` and `build_clipboard_payload([...])` outputs are
     byte-identical literals.

   Whole-tuple equality is deliberately **not** pinned — appending fields changes
   tuple length and equality by construction. Say so in the class docstring so
   the omission reads as a decision, not a gap.

2. **[`discriminate_priced_vs_unpriced_worsens`]** Write, **before the field
   shape is implemented**, the test that fails unless the parser distinguishes
   **three** states, all named explicitly:
   - `… Worsens: nothing. …` → `worsens == ()` (priced, empty);
   - no `Worsens:` sentence at all → `worsens is None` (not priced);
   - `… Worsens: simplicity(low). …` → populated tuple.

   A two-state implementation (empty-vs-populated) must fail it. Assert
   `worsens is None` / `worsens == ()` **identity-wise** — `assertFalse` passes
   for both and would make the test vacuous.

### Main implementation

3. **Implement the grammar** in `.aitask-scripts/monitor/concern_parser.py`:
   - `ImpactEntry = NamedTuple("ImpactEntry", [("dimension", str), ("magnitude", str)])`
     — magnitude already normalized (`""` = unspecified).
   - Import `concern_dimensions` as a sibling with the **same try/except
     relative-then-flat fallback used for `ansi_utils`** (line ~104); the module
     stays pure (`concern_dimensions` has an explicit purity contract).
   - Extend `_TRAILER_SENTENCE` with three alternatives built from
     `concern_dimensions.dimensions_pipe()`:
     - entry = `(?:<closed-alternation>)(?:\(\w{1,16}\))?`; list =
       `entry(?:\s*,\s*entry)*`;
     - `Improves:\s*<list>` / `Worsens:\s*(?:nothing|<list>)` /
       `Effort:\s*\w{1,16}`;
     - keep `_TRAILER_SPAN = (?:\s*SENTENCE)+\s*$` **verbatim** — terminal
       anchoring and free sentence order are preserved, and an invalid sentence
       simply is not part of the matched suffix run.
   - Append to `Concern`, **after** the existing fields, with defaults:
     `improves: tuple[ImpactEntry, ...] | None = None`,
     `worsens: tuple[ImpactEntry, ...] | None = None`, `effort: str = ""`.
     Docstring states `None` = sentence absent (not priced) vs `()` =
     `Worsens: nothing.` (priced as nothing), and why the distinction is
     load-bearing.
   - Extend `_parse_trailer` to return
     `(disposition, verdict, improves, worsens, effort)`, extracting each
     sentence from the matched span with per-sentence regexes that mirror
     `_DISPOSITION_IN_TRAILER`. **Lowercase each dimension name** (finding 1) and
     `normalize_magnitude` each token; normalize the `Effort:` token the same way
     (`""` when unrecognised — never `low`).
   - `display_body()` needs **no change**: it already removes exactly the matched
     span.
   - Update the module docstring's derived-fields bullet to name the three new
     fields. Leave every marker-grammar claim unchanged.

4. **Vector-grammar test class**, beyond steps 1–2:
   - missing magnitude (`robustness` → `("robustness", "")`); unknown magnitude
     (`robustness(extreme)` → `("robustness", "")`, **never** `low`);
   - **mixed-case dimension normalizes** — `Improves: Robustness(High).` →
     `("robustness", "high")` and is stripped from `display_body()` (finding 1;
     without this the parser emits a dimension outside the closed vocabulary for
     text the user can no longer see);
   - **recognized `Effort:` is actually derived** — `Effort: low|medium|high` →
     `effort == "low"|"medium"|"high"`, plus `Effort: High.` → `"high"` for case
     normalization, asserted **independently of any stripping or ordering
     assertion**. This is the positive control for the scalar: without it, an
     implementation that matches the `Effort:` sentence for stripping but never
     assigns the field still passes every other test here, because the residual
     test (step 6) and the absent-sentence case both expect `""`;
   - **duplicate sentence: first wins — parameterized over all three new
     extractors**, `Improves:` / `Worsens:` / `Effort:` (finding 2). One
     subTest per field, not a single `Disposition:`-shaped example: the three
     are separate regexes at separate call sites, so one written last-wins
     (e.g. `findall()[-1]`) would otherwise regress undetected. Keep
     `Disposition:` in the same parameterization as the reference case;
   - **empty / trailing-comma entry list fails the sentence** and stays visible,
     so `improves` is never `()` (finding 3);
   - unknown dimension on each side — whole sentence unparsed, visible in
     `display_body()`, and a valid suffix after it still parsed;
   - sentence-order freedom; multi-entry lists;
   - `derive_priority` over parsed `improves` (empty, all-unknown, mixed);
   - clipboard forwards `.body` verbatim with the full trailer.

5. **Contract sweeps.** `tests/test_concern_body_display_contract.py` must stay
   green **untouched** — its AST role map governs `.body` vs `display_body()`,
   and this change adds no new Concern-body read. Confirm rather than assume.

### Post-phase (risk mitigations)

6. **[`pin_effort_overstrip_residual`]** Pin, as a test, what the
   bounded-permissive `Effort:` alternative deliberately does **not** buy: a body
   ending `… reduces Effort: significantly.` has that sentence stripped from
   `display_body()` and yields `effort == ""`. Name the test for the accepted
   limit, not for a bug, and state in its docstring why the exposure is the
   settled design — an unrecognised token must yield unspecified rather than fail
   the sentence, so a closed `high|medium|low` class is not an option here. This
   records the residual so a later reader meets a documented decision instead of
   rediscovering it as a defect.

## Verification

- `python3 -m pytest tests/test_concern_parser.py tests/test_concern_body_display_contract.py tests/test_concern_dimensions.py -q`
  (baseline before any edit: 169 passed).
- Step 1's characterization class **observed passing before step 3's first
  edit** — record that run in the Final Implementation Notes.
- `bash tests/run_all_python_tests.sh --test-dir tests` — read only the last
  line (`PYTHON SUITE: PASSED|FAILED`); piping discards the exit status.

## Post-Implementation

Standard Step 9. Note for t1636_3 / _4 / _5: `ImpactEntry` and the three new
`Concern` fields are the consumer surface — **do not add consumers here**.

## Risk

### Code-health risk: low
- `_TRAILER_SPAN` is the single derivation point that every existing
  disposition/verdict derivation *and* `display_body()` strip depend on; widening
  its alternation with three sentence kinds could over-strip prose ·
  severity: low (residual — a byte-identical back-compat baseline is pinned
  before the regex is edited) ·
  → mitigation: inline pre-phase characterize_parser_backcompat
- Appending fields to the `Concern` NamedTuple has a positional-construction
  blast radius across the parser and ~40 constructions in the test modules ·
  severity: low (residual — the five-field projection and five-arg positional
  construction are pinned by the same pre-phase) ·
  → mitigation: inline pre-phase characterize_parser_backcompat
- `Effort:\s*\w{1,16}` is the one new alternative **not** drawn from a closed
  vocabulary, so a body ending `… reduces Effort: significantly.` is stripped
  from the display. This is the settled bounded-permissive design (an
  unrecognised token must yield unspecified, not fail the sentence), so the
  exposure is accepted, not removed · severity: low ·
  → mitigation: inline post-phase pin_effort_overstrip_residual

### Goal-achievement risk: low
- Collapsing "priced as nothing" (`()`) with "not priced" (`None`) would delete
  the anti-overengineering mechanism that is the feature's whole point ·
  severity: low (residual — a three-state discriminator is written before the
  field shape is chosen) ·
  → mitigation: inline pre-phase discriminate_priced_vs_unpriced_worsens
- `re.IGNORECASE` on the span means a mixed-case dimension name is stripped from
  the display body while yielding a name outside the closed vocabulary, which
  t1636_4's picker would render as an empty label for text the user can no longer
  see · severity: low (addressed directly by step 3's lowercase normalization and
  step 4's explicit test — not deferred) · → mitigation: none — fixed in-plan

### Planned mitigations
- timing: pre-phase | name: characterize_parser_backcompat | type: test | priority: high | effort: low | inline_risk: low | added_complexity: low | addresses: code-health — trailer regex is the single derivation point; Concern positional blast radius | desc: pin the five-field projection, five-arg positional construction, and display/clipboard byte-identity for no-trailer and disposition-only blocks, observed passing before _TRAILER_SPAN is edited
- timing: pre-phase | name: discriminate_priced_vs_unpriced_worsens | type: test | priority: high | effort: low | inline_risk: low | added_complexity: low | addresses: goal-achievement — collapsing "priced as nothing" with "not priced" deletes the mechanism | desc: three-state test (nothing / absent / populated) written before the field shape is chosen, asserted identity-wise so it cannot pass vacuously
- timing: post-phase | name: pin_effort_overstrip_residual | type: test | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: code-health — the permissive Effort: alternative strips prose ending in "Effort: <word>" | desc: pin the accepted over-strip residual as a test naming it a settled design limit, so it is not later rediscovered as a defect

## Post-Review Changes

### Change Request 1 (2026-08-30 17:20)
- **Requested by user:** The `if __name__ == "__main__": unittest.main()` guard
  sat above the four newly appended t1636_2 test classes, so
  `python3 tests/test_concern_parser.py` ran 122 tests and exited OK while pytest
  and `unittest discover` collected 147. The file's own direct-run entry point
  gave a false green that omitted all 25 new parser checks. Verified: CONFIRMED —
  reproduced exactly (122 vs 147) before the fix.
- **Changes made:** Moved the guard to be the last statement in the file, and
  added a comment stating *why* it must stay there, so a future append does not
  silently recreate the same false green. Both entry points now report 147.
- **Files affected:** `tests/test_concern_parser.py`
- **Root cause worth noting for siblings:** appending test classes with a shell
  heredoc (`cat >>`) lands them after any trailing `__main__` guard. t1636_3 /
  _4 / _5 will extend this same module — check the guard is still last after
  appending.

## Final Implementation Notes

- **Actual work done:** Exactly the approved plan, in order. `concern_parser.py`
  gained a sibling import of `concern_dimensions` (relative-then-flat fallback,
  matching `ansi_utils`), the `_IMPACT_ENTRY` / `_IMPACT_LIST` builders over
  `dimensions_pipe()`, three new alternatives in `_TRAILER_SENTENCE`, per-sentence
  extractors (`_IMPROVES_IN_TRAILER` / `_WORSENS_IN_TRAILER` /
  `_EFFORT_IN_TRAILER` / `_IMPACT_ENTRY_PARTS`), a new `ImpactEntry` NamedTuple,
  three appended `Concern` fields, and a `_parse_trailer` returning the 5-tuple.
  `_TRAILER_SPAN` and `display_body()` are byte-unchanged. Tests: four new
  classes, 25 checks.
- **Pre-phase observation (required by the plan):**
  `TestFiveFieldProjectionBackCompat` was written first and observed
  **PASSING against the unmodified `concern_parser.py`** — `5 passed, 122
  deselected` — before any parser edit. `TestWorsensIsPricedOrUnpriced` was then
  written and observed **FAILING** (`4 failed`, `AttributeError` on `worsens`)
  before the field shape existed, which is what proves it discriminates.
- **Deviations from plan:** None in approach. One addition beyond the written
  steps: `_parse_entries()` was extracted as a helper rather than inlined twice
  in `_parse_trailer`, since the improve and worsen sides parse identically.
- **Issues encountered:**
  - `_TRAILER_SPAN` carries `re.IGNORECASE`, so the closed dimension alternation
    matches case-insensitively too. `Improves: Robustness(High).` is therefore
    *stripped from the display body*, and a naive extractor would store
    `("Robustness", "")` — a name outside `VALID_DIMENSIONS` — describing text
    the user can no longer see. Fixed by lower-casing the name in
    `_parse_entries`, mirroring what the trailer already did for `disposition`
    (`.lower()`) and `verdict` (`.upper()`). Found during plan re-verification,
    not during coding.
  - Post-review: the appended test classes landed *after* the module's trailing
    `if __name__ == "__main__": unittest.main()` guard, so
    `python3 tests/test_concern_parser.py` ran 122 tests and exited OK while
    pytest collected 147 — a false green on the file's own direct-run entry
    point. Guard moved to the end of the file with a comment pinning why it must
    stay there. See Post-Review Changes above.
- **Key decisions:**
  - `Worsens: nothing` yields `()` *for free*: `_IMPACT_ENTRY_PARTS.finditer`
    finds no dimension name in the literal `nothing`. The three-state
    distinction therefore falls out of the grammar rather than needing a special
    case.
  - `improves` can only ever be `None` or non-empty — an empty or
    trailing-comma entry list fails the sentence, and only `Worsens:` accepts
    `nothing`. So `()` is a deliberate statement, never an accident of parsing.
  - Duplicate sentences resolve **first-wins** for all five extractors, matching
    what `Disposition:` already did. Pinned as a parameterized test rather than
    left implicit, because the five extractors are five separate regexes at five
    separate call sites.
  - The permissive `Effort:\s*\w{1,16}` over-strip is recorded as an accepted
    limit (`TestEffortOverStripIsAnAcceptedLimit`), not silently tolerated. It
    costs display only — `build_clipboard_payload` reads `.body`, so nothing is
    ever dropped from what the followed agent receives.
- **Upstream defects identified:** None
- **Notes for sibling tasks:**
  - **Consumer surface for t1636_3 / _4 / _5:** `ImpactEntry(dimension,
    magnitude)` and `Concern.improves` / `.worsens` / `.effort`. `None` vs `()`
    on the two vector sides is load-bearing — render them differently.
    `magnitude == ""` means *unspecified* and must render as `?`, never as `low`.
  - The marker priority is NOT derived here: `Concern.priority` is still the
    producer's marker value. t1636_4 should compare it against
    `concern_dimensions.derive_priority(c.improves)` and flag a disagreement
    rather than reconcile it silently (per `concern-format.md`).
  - `tests/test_concern_body_display_contract.py` stayed green and **byte
    untouched** — this change adds no new Concern-body read. Any sibling that
    reads `.body` or `display_body()` in `monitor/` must register its ROLE there
    or that guard fails closed.
  - **Appending to `tests/test_concern_parser.py` with `cat >>` puts your classes
    after the `__main__` guard.** Verify `python3 tests/test_concern_parser.py`
    and `pytest` report the same count before you call it done.
