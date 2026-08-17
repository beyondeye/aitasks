---
priority: medium
effort: low
depends: [t1544_4, t1544_5]
issue_type: documentation
status: Ready
labels: [documentation, web_site, reporting]
gates: [risk_evaluated]
anchor: 1544
created_at: 2026-08-17 22:07
updated_at: 2026-08-17 22:09
---

## Context

Sixth child of t1544 (backlog level + net flow by category in `ait stats`).
Parent plan: `aiplans/p1544_stats_backlog_and_net_flow_by_category.md`.
Depends on **t1544_4** (CLI) and **t1544_5** (TUI) — it documents what those two
actually shipped, so read both Final Implementation Notes before writing.

This is a **first-class docs child, not a verification afterthought**, per
`aidocs/framework/planning_conventions.md` §"User-facing features: docs are a
plan deliverable". It also carries real pre-existing errors to fix, independent
of the new feature.

## Pre-existing errors to fix (verified during t1544 planning)

1. **`website/content/docs/tuis/stats/_index.md`** — "Four presets ship with the
   framework, each bundling three panes", with a four-row table. There are
   already **six** presets (`overview`, `labels`, `agents`, `velocity`,
   `pipeline`, `sessions`) and they do **not** all bundle three panes (`agents`
   has four, `pipeline` has two). With `backlog` it becomes seven.

2. **`website/content/docs/tuis/stats/_index.md`** — "Presets are defined in
   `aitasks/metadata/stats_config.json` and are read-only at runtime" is
   **factually wrong**. They are defined in
   `.aitask-scripts/stats/stats_config.py::DEFAULT_PRESETS`. The JSON is an
   **optional project-local override layer**: `load_layered_config` merges it
   with `deep_merge`, which merges **dicts per key** and **replaces lists**. So a
   preset key present only in the code still appears, while a preset *list*
   pinned in the JSON replaces the code list for that preset. Document that
   precedence — it is exactly the contract t1544_5's precedence test pins, so the
   doc and the test must describe the same thing.

   The "Config persistence" section further down describes the project/user layer
   split correctly; reconcile the two passages rather than leaving them in
   conflict.

## New-feature documentation

3. **`website/content/docs/commands/board-stats.md`**
   - The `ait stats` option table gains `--backlog-weeks N` and
     `--csv-backlog [FILE]`.
   - The numbered "Statistics provided" list gains the two new sections.
   - The **"CSV export format"** line pins the exact 10-column list; it becomes
     12 (`created_at`, `category` appended). State explicitly that open tasks are
     **not** rows in that table, so the backlog level is not reproducible from
     it — the series lives in `--csv-backlog`. Document the new file's columns:
     `week_ending, category, open, arrived, departed, net`.
   - The **"Data sources"** paragraph already documents the completion fallback
     chain for the existing counters. Extend it: the backlog sections use
     `completed_at` (falling back to `updated_at` for `Done`/`Completed`), **not**
     the `merge_approved`/`review_approved` ledger stamps the other sections
     prefer — so the two can name a different week for ~0.3% of tasks. Also state
     that the backlog population scans **active** tasks as well as archived ones,
     that a `Done`-but-unarchived task counts as departed, that **Postponed**
     tasks count as open, and that **Folded** tasks are excluded.

4. **`website/content/docs/tuis/stats/_index.md`** — add the `backlog` preset row
   and describe the two new panes in the presets table.

5. **`website/content/docs/skills/aitask-stats.md`** — update the description of
   what the report contains.

6. Check whether `website/content/docs/tuis/_index.md` mirrors a per-TUI pane or
   preset list; update it if so.

## Conventions to follow

Read `aidocs/framework/documentation_conventions.md` first. In particular:

- **Current-state only** — describe what the tool does now. No version history,
  no "as of vX", no "newly added" framing in the doc body.
- Genericize any passage that names specific coding agents.
- If a passage is being corrected rather than extended, correct it outright —
  do not add a second, contradicting sentence next to the wrong one.

## Key files to modify

- `website/content/docs/commands/board-stats.md`
- `website/content/docs/tuis/stats/_index.md`
- `website/content/docs/skills/aitask-stats.md`
- `website/content/docs/tuis/_index.md` (only if it mirrors the pane/preset list)

## Verification steps

```bash
cd website && npm install && hugo build --gc --minify
```

- Build succeeds with no broken `relref` links.
- Every number and column list in the docs matches the shipped behaviour — check
  against live output, not against the plan:
  ```bash
  ./ait stats --help
  ./ait stats --csv /tmp/t.csv --csv-backlog /tmp/b.csv && head -1 /tmp/t.csv && head -1 /tmp/b.csv
  ```
- The preset count in the prose matches
  `.aitask-scripts/stats/stats_config.py::DEFAULT_PRESETS`.
