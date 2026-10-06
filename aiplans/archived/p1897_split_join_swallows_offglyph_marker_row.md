---
Task: t1897_split_join_swallows_offglyph_marker_row.md
Branch: main
Base branch: main
Output branch: main
---

# t1897 — split rejoin swallows a following item in another glyph

## Context

`_join_split_marker` (`.aitask-scripts/monitor/concern_parser.py`) rejoins a
`[priority | region]` bracket that an agent TUI hard-wrapped across rows. Its
stops are: the next row starts an item in the block's glyph; and, **in probe
mode only**, an opposite *accepted*-glyph row whose `_yield_table` entry is True.
So within the 3-row envelope it swallows, silently, any following item that is

- in an unaccepted glyph, one-row: `• [medium | missing` / `◦ [high | next] body`
  → one fabricated concern, `unrecovered_markers == []` (pinned today by
  `test_split_join_consumes_a_marker_looking_row_known_gap`);
- in an unaccepted glyph, **split**: `• [medium | missing` / `◦ [high | next` /
  `region] next concern body` → fabricated region `missing ◦ [high | next region`
  (review finding: a same-row-closure check alone would miss this);
- in the opposite accepted glyph, **split, in scan mode** after an established
  item: `- [low | a] b` / `- [medium | missing` / `• [high | real` / `region] body`
  (scan mode passes no `boundary`, so the opposite-glyph stop never applies).

Constraint (t1892 review): the stop must not become the broad `_MARKER_LIKE`
shape. `— [reference] body` is a genuine bracket continuation and must keep
rejoining, and so must its split form (`— [ref and more` / `stuff] body`). The
probe stays iterative (back-to-front table, no recursion).

## Approach

Widen the **one** existing boundary definition rather than adding a second rule:
`_yield_table` answers "does a genuine item start here, read in its own glyph?"
for **every marker-looking glyph** (`_MARKER_LIKE`'s class), not only the
accepted ones. A row yields when it is a complete one-row item in its own glyph,
or its own split rejoin (probe mode) succeeds. Then:

- `_block_glyph` picks the first yielding row **whose glyph is accepted**, so an
  off-glyph item still never becomes the block glyph or a concern (accepting is
  unchanged).
- `_join_split_marker` stops at a next row that yields, in **both** probe and
  scan mode (`_scan_items` passes the table it already computes).

`— [reference] …` (no `|`, not a priority word) yields nothing, one-row or split,
so it keeps joining. After a stop, the unclosed row fails its join and is
reported, and the stopping row is reported by `_MARKER_LIKE`. Following an
established item, both stay in that item's body, so nothing is removed.

Prototyped in memory against all of `tests/test_concern_parser.py`, plus the
three scenarios above, the one-row and region-less off-glyph rows and both
punctuation fragments. Every scenario gives the intended result. Only the two
subtests of the known-gap test change; the other 205 tests pass.

## Implementation

1. **`.aitask-scripts/monitor/concern_parser.py`**
   - Add `_ANY_GLYPH = r"[^\w\s\[\]]"` and build `_MARKER_LIKE` from it (same
     regex). Add `_MARKER_START_ANY = rf"^\s*(?P<glyph>{_ANY_GLYPH})\s+\["`.
   - Factor the shared tail of `_ITEM` / `_ITEM_NO_REGION` into string
     fragments and add `_ITEM_ANY` / `_ITEM_NO_REGION_ANY` (same groups, glyph
     class `_ANY_GLYPH`; region-less keeps the closed `high|medium|low`
     vocabulary and `re.IGNORECASE`). `_ITEM` / `_ITEM_NO_REGION` stay as they
     are for acceptance in `_scan_items`.
   - `_yield_table`: iterate rows matching `_MARKER_START_ANY`. One-row yield
     uses `_ITEM_ANY` / `_ITEM_NO_REGION_ANY`, and the split probe uses the row's
     own glyph. The table is still built back to front with no recursion. Update
     the docstring: the boundary covers any marker-looking glyph, while
     acceptance is decided separately.
   - `_block_glyph`: return the glyph of the first yielding row that also
     matches `_MARKER_START` (accepted). Update the docstring.
   - `_join_split_marker`: make `boundary` a required `list[bool]`. Stop when
     `_MARKER_START_ANY.match(nxt)` and (its glyph `== glyph` or
     `boundary[nxt_idx]`). Match the rejoined text with `_ITEM_ANY`, which is
     equivalent to `_ITEM` when the start row has an accepted glyph, and is needed
     for an off-glyph probe. Rewrite the docstring: one boundary rule for both
     modes, `— [reference]` still joins, the accepted residual.
   - `_scan_items`: keep the table (`yields = _yield_table(lines)`) and pass
     `boundary=yields` to the scan-mode join. Docstring: drop the "one known
     gap" sentence.
   - `_MARKER_LIKE` comment: replace "Known gap…" with the new relationship. The
     report shape still never steers parsing. The split stop is the yield table,
     which needs an item shape in its own glyph.

2. **`tests/test_concern_parser.py`** (`TestCodexBulletMarkers`, using its
   `_glyph()` / `_fields()` helpers)
   - Replace `test_split_join_consumes_a_marker_looking_row_known_gap` with
     `test_split_join_stops_at_a_one_row_item_in_any_glyph`. For each lead glyph
     in (`-`, `•`), the next row is `◦ [high | next] next concern body`. Expect
     `parse_concerns == []` and `unrecovered_markers ==` both rows.
   - `test_split_join_stops_at_a_split_item_in_any_glyph` (leading case, the
     review's repro). For lead glyphs (`-`, `•`), use `◦ [high | next` and
     `region] next concern body`. Expect `[]`, both marker rows reported, and
     `"missing"` absent from the clipboard payload.
   - `test_established_block_stops_at_a_split_item_in_another_glyph`. Rows:
     `- [low | a] b`, `- [medium | missing`, `{g} [high | real`, `region] body`,
     for `g` in (`•`, `◦`). Expect exactly one concern `("low", "a", …)` whose
     body carries the rows (nothing removed), and both marker rows reported.
   - `test_region_less_item_in_any_glyph_stops_the_join`: `◦ [high] next body`.
   - `test_item_shaped_region_fragment_stops_the_join_accepted_residual`:
     `- [medium | long context`, `— [a | b] body` → `[]`, both reported (pins
     the residual as a decision).
   - Add to `TestSplitMarkerJoin`
     `test_split_punctuation_led_region_fragment_is_still_rejoined`:
     `- [medium | a long`, `— [ref and more`, `stuff] body` →
     `("medium", "a long — [ref and more stuff", "body")`, nothing reported.
   - `test_long_three_glyph_unclosed_block_is_iterative`: `_DEEP_CAPTURE_ROWS`
     unclosed rows cycling `•`, `-`, `◦`, then `- [high | real] real body`. This
     pins the widened table as stack-safe: the real concern is recovered and the
     run reported.
   - Keep untouched (must pass): `test_punctuation_led_region_fragment_is_still_rejoined`,
     `test_nonparseable_opposite_glyph_fragment_does_not_end_the_probe`,
     `test_unclosed_leading_row_does_not_swallow_*`,
     `test_split_leading_marker_still_selects_its_glyph`, the long alternating
     tests and the at-bound and over-bound envelope tests.

3. **`.claude/skills/aitask-shadow/concern-format.md`** (the only tracked copy)
   - "Split-marker hazard" bullet: replace the known-gap passage. The lookahead
     stops at any following row that is itself an item in its own glyph, one-row
     or split within the envelope, in any marker-looking glyph (`◦ [high | next]
     …`). Both rows are then reported, and following an earlier item they stay
     in its body. Keep the `— [reference]` sentence (including its split form).
     State the residual and qualify the guarantee to the envelope: a region
     fragment that is itself item-shaped (`— [a | b]`) is indistinguishable and
     stops too, so it is reported rather than silent. A following item split
     wider than the envelope is outside the recovery bound, as already
     documented.
   - `unrecovered_markers` paragraph: remove "The one exception is a row
     consumed by a split-marker rejoin…". In "It never steers parsing", say the
     report shape still never steers. The split stop uses the item-shape
     boundary, not `_MARKER_LIKE`.

4. Step 9 (Post-Implementation): commit code, tests and doc as
   `bug: Stop split rejoin at a following item in any glyph (t1897)`, then
   archive per the workflow.

## Verification

- `python3 -m pytest tests/test_concern_parser.py -q`: all pass.
- Parser consumers: `tests/test_shadow_seam.py`,
  `test_concern_body_display_contract.py`, `test_monitor_concern_action.py`,
  `test_concern_picker_modal.py`, `test_minimonitor_concern_action.py`,
  `test_markup_colour_contract.py` (pytest), and
  `bash tests/test_shadow_spinoff_create_contract.sh`.
- Full suite: `bash tests/run_all_python_tests.sh`. Read only the final
  `PYTHON SUITE:` verdict line.

## Risk

### Code-health risk: low
- Widening the yield table to every marker-looking glyph changes the probe's boundary set (the same function also chooses the block glyph). A mistake could demote a valid item or change which glyph is chosen. Bounded: `_block_glyph` still filters to accepted glyphs, the prototype passes every existing glyph and probe guard, and new tests pin the leading, established and deep-block cases · severity: low · → mitigation: none (covered by the step-2 tests)
- A genuine region fragment that is itself item-shaped (`— [a | b] …`) now stops the join. That concern is lost but REPORTED, where before it was joined. This is implausible for a region and cannot be told apart from an off-glyph item · severity: low · → mitigation: none (accepted residual, pinned in step 2, documented in step 3)

### Goal-achievement risk: low
None identified.

## Implementation Progress

- [x] Step 1 — `concern_parser.py`: `_ANY_GLYPH`, shared `_ITEM_TAIL` /
  `_ITEM_NO_REGION_TAIL`, `_ITEM_ANY` / `_ITEM_NO_REGION_ANY`,
  `_MARKER_START_ANY`; `_yield_table` covers every marker-looking glyph;
  `_block_glyph` filters to accepted glyphs; `_join_split_marker` takes a
  required `boundary` and stops on it in both modes; `_scan_items` passes it.
- [x] Step 2 — tests replaced/added as planned (213 pass). Red proof: the HEAD
  parser injected in memory fails 8 of the new assertions (all behaviour
  tests, both established-block subtests); the two guard tests pass on HEAD as
  intended.
- [x] Step 3 — `concern-format.md` known-gap passage, `unrecovered_markers`
  exception and "never steers parsing" bullet rewritten.

## Post-Review Changes

### Change Request 1 (2026-10-05, plan review — before implementation)
- **Requested by user:** the first plan's `_ITEM_SHAPED` same-row guard still
  swallowed a following *split* item (`◦ [high | next` / `region] …`) and, in
  scan mode, a split opposite-accepted-glyph item after an established concern.
- **Changes made:** replaced the separate guard with a widened `_yield_table`
  boundary (every marker-looking glyph, one-row or split) applied in both probe
  and scan mode; added leading, established-block, split-punctuation and deep
  three-glyph tests.
- **Files affected:** plan only (pre-implementation).

## Final Implementation Notes
- **Actual work done:** as planned. `concern_parser.py` gains `_ANY_GLYPH`,
  shared item tails, `_ITEM_ANY` / `_ITEM_NO_REGION_ANY` / `_MARKER_START_ANY`;
  `_yield_table` answers for every marker-looking glyph; `_block_glyph` picks
  only accepted glyphs; `_join_split_marker` requires `boundary` and stops on it
  in both modes (rejoined text matched with `_ITEM_ANY`); `_scan_items` passes
  its table. The known-gap test is replaced by seven tests pinning the new
  boundary, the residual and stack safety; `concern-format.md` updated.
- **Deviations from plan:** none.
- **Issues encountered:** a first red-proof attempt copied the HEAD parser into
  scratch and failed on missing sibling modules / fixtures (setup crash, not a
  red result). Replaced by injecting the HEAD module in memory and running the
  real test file in place: 8 assertions fail on HEAD, all pass now.
- **Key decisions:** stop rather than "consume but report" — a consumed row
  forwards a concern fabricated from two findings. Acceptance is unchanged
  (`_ITEM` / `_ITEM_NO_REGION` / `_MARKER_START` in scan mode); only the
  boundary widened. Accepted residual: an item-shaped region fragment
  (`— [a | b]`) stops the join and is reported.
- **Upstream defects identified:** None
