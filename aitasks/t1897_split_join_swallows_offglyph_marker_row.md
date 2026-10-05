---
priority: medium
effort: low
depends: []
issue_type: bug
status: Implementing
labels: [shadow, aitask_monitormini, tui, codex]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
anchor: 1892
followup_kind: upstream_defect
implemented_with: claudecode/opus5_5
created_at: 2026-10-05 23:40
updated_at: 2026-10-06 00:38
---

## Origin

Spawned from t1892 during Step 8b review.

## Upstream defect

- `.aitask-scripts/monitor/concern_parser.py:_join_split_marker` — a split
  rejoin whose unclosed bracket is followed, within the envelope, by a
  marker-looking row in a non-accepted glyph (`◦ [high | next] …`) swallows
  that row into the region and never reports it. It predates t1892 and is
  identical with a dash first marker. It is pinned by
  `test_split_join_consumes_a_marker_looking_row_known_gap`. Changing the
  recovery must keep
  `test_punctuation_led_region_fragment_is_still_rejoined` passing.

## Diagnostic context

From the t1892 review (Change Request 1, finding b; confirmed):

- A complete block with `• [medium | missing closing bracket` followed by
  `◦ [high | next] next concern body` produces one concern, with region
  `missing closing bracket ◦ [high | next]`, and `unrecovered_markers`
  returns `[]`. A dash first marker gives the same result on the pre-t1892
  parser.
- t1892 qualified the doc's "reported rather than silent" claim with this
  exception (`concern-format.md`, the "Split-marker hazard" known-gap note,
  and the `unrecovered_markers` paragraph). It deliberately left the recovery
  unchanged.
- **The constraint any fix must respect.** The join stop must not become the
  broad `_MARKER_LIKE` shape. A punctuation-led region fragment
  (`— [reference] …`) is a genuine continuation of the bracket and must keep
  rejoining; t1892's review measured that the broad stop turns it into
  0 concerns plus 2 lost-marker reports. Likewise, the glyph probe's boundary
  rule (`_yield_table`: stop at same-glyph rows and at opposite-glyph rows
  that yield an item) must keep its pinned guards passing.

## Suggested fix

Distinguish a region fragment from an unaccepted-glyph *item* (e.g. a row
whose bracket closes and has the full `[word | region]` shape). Either stop
the join at it, or report it even when it is consumed. Pin the
punctuation-led fragment, the probe guards and the long-block tests while
doing so.

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-10-05T21:38:50Z status=pass attempt=1 type=human
