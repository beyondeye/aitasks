---
Task: t1357_4_step_timing_drift_report.md
Parent Task: aitasks/t1357_task_workflow_step_stats_and_drift.md
Sibling Tasks: aitasks/t1357/t1357_1_*.md … t1357_7_*.md
Archived Sibling Plans: aiplans/archived/p1357/p1357_*_*.md
Worktree: aiwork/t1357_4_step_timing_drift_report
Branch: aitask/t1357_4_step_timing_drift_report
Base branch: main
Output branch: main
---

# Plan: t1357_4 — Step timings + WoW/MoM drift in `ait stats`

Input contract: event schema v1 in the parent plan § Architecture (PINNED);
files under `aitasks/metadata/stats/events/<YYYY-MM>/*.jsonl`
(`t<id>_<run>.jsonl` + optional `t<id>_<run>_enrich.jsonl` from t1357_5 —
design the loader to tolerate/skip `_enrich` files it doesn't yet consume).

## Implementation steps

1. **Read first:** `lib/stats_data.py` (root resolution ~47, `PhaseTimings`
   ~127, `_span_hours` ~941, `format_duration` ~309, `collect_stats` ~1006),
   `aitask_stats.py` (`render_pipeline_timing` ~228, `render_text_report`
   ~258, `write_csv` ~477), `stats/stats_config.py` layering.
2. **`lib/stats_step_data.py`** (the ONE validated reader):
   - `load_step_events(root) -> StepEventStore`: glob monthly dirs, parse
     rows, validate v/required fields, collect `malformed` diagnostics
     (count + first N examples) without crashing.
   - Pairing: (run, step, sub) begin→end durations; expose unpaired-begin
     counts. Point-derived spans: claim→first planning event,
     gates timeline. Partial timelines are valid.
   - Bucketing: dataclass sample = (duration_s, ts, step, sub, agent → split
     codeagent/model like stats_data does for `implemented_with`, effort,
     profile, skill, src); indexes by ISO week (`%G-W%V`) and month (`%Y-%m`).
   - `compute_drift(samples, threshold_pct, min_samples)` → per step (and
     step×codeagent where both cells ≥ min_samples): current vs previous
     week, current vs previous month; returns flagged entries with Δ%,
     medians, Ns. Pure function — unit-testable without I/O.
3. **`aitask_stats.py`**: `render_step_timings()` + `render_drift()` sections
   appended to the text report (mirror pipeline-timing style: header,
   aligned columns, `format_duration`); `--csv-steps <file>` flag writing one
   row per sample. Empty store → one-line "no step data" per section.
4. **Config:** `drift_threshold_pct` (20) / `drift_min_samples` (3) read via
   the layered stats config; add defaults to
   `aitasks/metadata/stats_config.json` AND the seed copy if one exists in
   `seed/` (check — per-op defaults memory: new keys need seed+live).
5. **`aitask-stats` SKILL.md:** document new sections + flags; refresh the
   stale section list (it predates code-agent/pipeline/verified sections).
6. **Tests:** new module under the python test dir the suite runner scans
   (mirror an existing stats test's location/naming): fixture event files
   covering the task's Verification list — pairing, malformed rows,
   week/month boundaries, drift positive case (one step's median doubles →
   exactly that step flagged), negative controls (identical periods → no
   flags; big Δ under min_samples → no flags).

## Verification

- `bash tests/run_all_python_tests.sh --test-dir <dir>` → last line
  `PYTHON SUITE: PASSED` (never trust intermediate "Results:" lines; use
  PIPESTATUS if piping).
- `./ait stats` end-to-end on real data (or empty store) renders cleanly.

## Step 9

Standard Step 9.
