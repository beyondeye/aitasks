---
priority: medium
effort: low
depends: []
issue_type: bug
status: Ready
labels: [artifacts, trails, tui, aitask_board]
gates: [risk_evaluated]
anchor: 1210
followup_kind: upstream_defect
created_at: 2026-08-16 11:01
updated_at: 2026-08-16 11:01
---

## Origin

Spawned from t1505_3 during Step 8b review.

## Upstream defect

- `.aitask-scripts/board/aitask_board.py:4092-4094` — the trail detail modal's
  `line()` helper treats a whitespace-only string as present, so a
  schema-valid whitespace-only `problem_statement` / `recommendation_summary` /
  `method_note` renders as a labelled line with blank content.

The guard is `if value in (None, "", [], {}): return`, which catches the empty
string but not `"   "` or `"\n"`.

## Diagnostic context

t1505_3 added `narrative.overview` and had to decide how strictly to constrain
it. That surfaced a disagreement between the two shipped renderers of trail
narrative prose:

- `trail_summary_text()` (`aitask_board.py:800-822`) strips, and treats a
  whitespace-only value as **absent** — it falls through to the next field.
- `TrailDetailScreen._sections()`'s `line()` (`:4092-4098`) does **not** strip,
  so the same value renders as a labelled line with blank content.

t1505_3 closed this for `overview` alone, at the schema boundary
(`"pattern": "\\S"`), because the field was brand new and tightening it
invalidated no stored document. **The legacy prose fields were deliberately
left alone**: `problem_statement`, `recommendation_summary`, `method_note` and
the per-entry `rationale` carry only `minLength: 1`, and adding a pattern to
them would invalidate every stored trail. So the defect is still reachable
through them.

Verified during t1505_3 (2026-08-16), against the current schema:

```
$ python3 .aitask-scripts/lib/trail_schema.py validate <gate_framework.json with problem_statement="   ">
VALID:trail-gate-framework-landing     # rc=0 — schema-valid
```

and `line("problem", "   ")` passes its `value in (None, "", [], {})` guard, so
the modal prints `problem: ` followed by blank content.

## Suggested fix

Make `line()` treat a blank-after-strip string as absent, matching
`trail_summary_text()`'s already-shipped semantics — the renderers should agree:

```python
def line(label, value):
    if value in (None, "", [], {}):
        return
    if isinstance(value, str) and not value.strip():
        return
    ...
```

Fixing it in the renderer (rather than by tightening the legacy schema fields)
is what keeps every stored trail valid. Pin it with a modal-level test asserting
no labelled line is emitted for a whitespace-only narrative field; the
`test_absent_narrative_overview_prints_no_empty_label` test in
`tests/test_board_bytrail_view.py` is the closest existing precedent.
