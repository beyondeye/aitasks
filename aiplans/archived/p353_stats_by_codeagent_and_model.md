---
Task: t353_stats_by_codeagent_and_model.md
Worktree: (none — current branch)
Branch: main
Base branch: main
---

# Implementation Plan for t353

## Summary

Extend `ait stats` so it reports implementation breakdowns by code agent and
LLM model using archived task `implemented_with` metadata. Keep the CLI surface
unchanged, add the new data to text output and CSV export, and render matching
histograms in `--plot` mode.

## Key Changes

1. Update `.aitask-scripts/aitask_stats.py`
   - Parse `implemented_with` from archived task frontmatter.
   - Normalize agent/model data, including known legacy values.
   - Track weekly counters for code agents and LLM models across the existing
     `W-3 .. This Week` buckets.
   - Add text-report sections for code agent and model weekly trends.
   - Extend CSV rows with raw and normalized implementation metadata.
   - Add four new plot summaries: code agents (4w and this week) and models
     (4w and this week).

2. Extend `tests/test_aitask_stats_py.py`
   - Add fixtures for canonical, legacy, and missing `implemented_with` values.
   - Verify normalization, weekly counters, rendered report sections, and CSV
     columns.

3. Update stats docs
   - Refresh `website/content/docs/commands/board-stats.md`.
   - Refresh `website/content/docs/skills/aitask-stats.md`.

## Defaults Chosen

- `1w` / `4w` use the existing week-bucket semantics already used by
  `ait stats`, not rolling 7/28 day windows.
- Missing or unparseable `implemented_with` values are counted under
  `unknown`.
- Recognizable legacy strings are normalized to current canonical buckets.

## Post-Implementation

- Revisit this plan with final implementation notes, deviations, and
  verification results.
- Complete Step 9 later if the task is formally finalized and archived.

## Final Implementation Notes

- **Actual work done:** Extended `.aitask-scripts/aitask_stats.py` to parse
  archived `implemented_with` metadata, normalize code-agent and LLM-model
  buckets (including known legacy values), add weekly trend tables for both,
  append raw and normalized implementation fields to CSV export, and render
  four additional `--plot` histograms for code agents and models.
- **Deviations from plan:** Model normalization was implemented from provider
  CLI IDs so equivalent models can collapse into shared buckets across agents
  where the underlying model is the same. Unknown or unmapped models keep the
  agent bucket when possible and fall back only the model dimension to
  `unknown`.
- **Issues encountered:** The repo stores task data through ignored symlinks
  into `.aitask-data/`, so only the local plan file was updated there; the
  tracked code/docs/tests remain the actual implementation diff.
- **Verification:** `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest
  tests.test_aitask_stats_py`, `PYTHONDONTWRITEBYTECODE=1 python3 -m py_compile
  .aitask-scripts/aitask_stats.py`, and a live `python3
  .aitask-scripts/aitask_stats.py --csv ...` run all passed. The live run
  confirmed the new code-agent/model sections and expanded CSV header.
