---
priority: low
effort: low
depends: []
issue_type: performance
status: Implementing
labels: [reporting, metrics, backlog]
assigned_to: dario-e@beyond-eye.com
anchor: 1544
followup_kind: risk_mitigation
created_at: 2026-08-24 16:18
updated_at: 2026-08-25 16:47
---

## Origin

Risk-mitigation ("after") follow-up for t1544_4, created at Step 8d after implementation landed.

## Risk addressed

code-health — the CSV category column costs a second resolve_category pass,
+62 ms / +25% on every ait stats and stats-TUI load.

Verbatim from t1544_4's plan `## Risk` section:

> The `category` column costs a second `resolve_category` pass over the archived
> tree — measured +62 ms on a 248 ms baseline (+25%), paid on every `ait stats`
> and every stats-TUI load, for a column that only materializes with `--csv`.
> · severity: medium · → mitigation: memoize_backlog_category

## Goal

Classify the archived tree **once**. `_accumulate_backlog`
(`.aitask-scripts/lib/stats_data.py`) already calls
`resolve_category(frontmatter, body, filename, tally=None)` at the end of its
guard chain; t1544_4's `csv_rows` producer calls it a second time for the same
files. Have the collection path expose the category it already resolves and
have the row producer consume it.

Two constraints that make this non-trivial, which is why it was spawned rather
than inlined:

1. **`_accumulate_backlog` returns early on every exclusion**, and it resolves
   the category only after all seven guards. A naive memo therefore yields an
   empty category for any task that is excluded from the backlog series but
   still has a `csv_rows` row (0 of 1845 today, but structurally reachable —
   e.g. a `folded` task carrying a `merge_approved` ledger stamp, which
   `resolve_completion_date` dates while the `folded` guard excludes it).
   Either hoist the resolution above the guards or fall back to a direct call
   on a memo miss; do not ship a silently-empty cell.
2. **The `with_backlog=False` contract must survive.**
   `tests/test_stats_multistage.py` asserts `resolve_category` is invoked
   **exactly zero** times under `collect_stats(with_backlog=False)`
   (`_check_with_backlog_off`), and that the `category` cell is empty in that
   mode while populated when on. Both assertions must keep passing unedited —
   if either fails, the memo leaked classification into the off path.

## Verification

- `bash tests/run_all_python_tests.sh --test-dir tests` — read the LAST line only.
- `tests/test_stats_multistage.py::_check_with_backlog_off` passes **unedited**.
- Measure the delta the way t1544_4 did: median of 5 `collect_stats(with_backlog=True)`
  runs over the real corpus, before and after. The target is the ~62 ms second
  pass, not the ~89 ms the backlog collection itself costs.
- `ait stats --csv <f>` still emits 12 columns with a non-empty `category` on
  every row.
