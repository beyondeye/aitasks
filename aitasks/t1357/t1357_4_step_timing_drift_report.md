---
priority: medium
effort: medium
depends: [t1357_3]
issue_type: feature
status: Ready
labels: [reporting, verifiedstats]
gates: [risk_evaluated]
anchor: 1357
created_at: 2026-07-31 10:57
updated_at: 2026-07-31 10:57
---

## Context

Fourth child of t1357. The event log now accumulates per-run JSONL files on
the task-data branch; this child builds the read side: per-step timing
aggregation and week-over-week / month-over-month drift detection in
`ait stats`, plus CSV export.

Parent plan: `aiplans/p1357_task_workflow_step_stats_and_drift.md`
(child t1357_4 section — the event schema there is the PINNED input
contract). Depends on t1357_1..3 (data must exist to report on), though the
loader is testable from fixtures alone.

## Key files to modify

1. **New `.aitask-scripts/lib/stats_step_data.py`** — the ONE validated
   reader for the event store:
   - Glob `aitasks/metadata/stats/events/<YYYY-MM>/*.jsonl` (resolve the dir
     via the same ARCHIVE_DIR-style root resolution `lib/stats_data.py` uses,
     ~line 47), parse + validate rows (`v==1`, required fields; count and
     expose malformed-row diagnostics, never crash).
   - Pair `begin`/`end` per (run, step, sub) → duration samples; derive
     point-to-point spans for coarse steps (claim→planning, gates sequence).
     Missing ends are tolerated (partial timeline).
   - Bucket samples by ISO week and calendar month × (step, sub, agent,
     model, effort, profile) — agent string splits into codeagent + model
     like `stats_data.py` does for `implemented_with`.
   - Drift: per step (and per step×agent when samples allow), compare median
     duration of current vs previous week AND current vs previous month;
     flag when |Δ%| > threshold AND both periods have >= min_samples.
2. **`.aitask-scripts/aitask_stats.py`** — two new sections following the
   existing render pattern (`render_pipeline_timing` ~line 228 is the
   model): "Step timings" (median/mean/N table per step × dims) and "Drift"
   (flagged steps with direction, Δ%, sample counts; WoW and MoM
   subsections). New `--csv-steps` export (one row per duration sample).
3. **Config:** `drift_threshold_pct` (default 20) and `drift_min_samples`
   (default 3) in `aitasks/metadata/stats_config.json` via the existing
   layered `stats/stats_config.py` (+ seed copy if stats_config ships in
   seed/ — check).
4. **`.claude/skills/aitask-stats/SKILL.md`** — document the new sections +
   flags; also refresh the stale section list (it predates the code-agent /
   pipeline-timing / verified-rankings sections).

## Reference files for patterns

- `lib/stats_data.py`: `PhaseTimings` (~127), `_span_hours` (~941),
  `format_duration` (~309), `collect_stats` (~1006).
- `aitask_stats.py`: `render_text_report` (~258), `write_csv` (~477).
- Python test conventions: `bash tests/run_all_python_tests.sh --test-dir
  <dir>`; read ONLY the last verdict line; beware the `-k` filter pitfall
  (no pytest ⇒ unittest ⇒ `-k "A or B"` runs 0 tests, exits 0).

## Verification

- New python test module with fixture event files:
  - Loader: valid + malformed rows, begin/end pairing, unpaired begin,
    dim bucketing, week/month boundary edges (ISO week vs calendar month).
  - Drift math: two synthetic months where exactly one step's median
    doubles → exactly that step flagged (MoM); same for weeks (WoW).
  - **Negative control:** identical periods → zero flags; below
    min_samples → zero flags even with a large Δ.
- `./ait stats` runs end-to-end against real accumulated data without error
  (sections render "no data" gracefully when the store is empty).
