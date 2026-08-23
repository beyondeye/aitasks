---
priority: medium
effort: low
depends: []
issue_type: bug
status: Ready
labels: [reporting, metrics]
anchor: 1544
followup_kind: upstream_defect
created_at: 2026-08-23 16:25
updated_at: 2026-08-23 16:25
---

## Origin

Spawned from t1544_3 during Step 8b review.

## Upstream defect

- `.aitask-scripts/lib/stats_data.py:1219-1220` — `collect_inflight` declares
  `today: date` and `week_start_dow: int` but references neither in its body;
  both are dead parameters every caller must still supply positionally.

## Diagnostic context

Found while wiring t1544_3's backlog arrival scan into `collect_inflight`'s
existing live-tree walk (via the new `on_file` observer). Reading the function
end-to-end to place the observer showed that neither date parameter is used
anywhere in the body: the classifier works purely from each file's content
(`has_gate_markers` / `derive_gate_runs` / `archive_status_from_text`), and the
one date it does produce comes from `_ledger_ts_to_date(review.run_id)`, not
from `today`.

Verified on live source:

```
awk '/^def collect_inflight/,/^def collect_stats/' .aitask-scripts/lib/stats_data.py \
  | grep -n "today\|week_start_dow" | grep -v "def \|today: date\|week_start_dow: int"
# (no output)
```

Pre-existing since t635_20; t1544_3 added the `on_file` parameter but
deliberately did not touch the signature, since removing parameters is a
different change with its own blast radius.

## Suggested fix

Drop both parameters and update every call site. The blast radius is small but
crosses module and test boundaries:

- `.aitask-scripts/lib/stats_data.py` — `collect_stats` calls it with
  `(today, week_start_dow, project_root=..., on_file=...)`.
- `.aitask-scripts/aitask_stats.py` — imports and re-exports `collect_inflight`
  in `__all__`, so the public surface changes.
- `tests/test_stats_multistage.py:_check_collect_inflight` — calls it
  positionally as `sd.collect_inflight(date(2026, 6, 29), 1, project_root=tmp)`.

Alternatively, keep the signature and document the two parameters as reserved —
but that is the weaker option, since a caller currently has to invent values for
arguments that cannot affect the result.
